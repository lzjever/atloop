"""LLM client wrapper for lexilux."""

import logging
import re
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from lexilux import Chat, ChatContinue, ChatHistory, ChatParams, ChatResult

# Note: ChatHistory is kept for backward compatibility but no longer used
from atloop.config.models import AtloopConfig
from atloop.llm.prompts import PromptLoader
from atloop.llm.schema import (
    VALID_TOOLS,
    ActionJSON,
    parse_action_json,
)
from atloop.skills import EnhancedSkillLoader

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM client wrapper with cache-optimized history management."""

    def __init__(self, config: AtloopConfig, workspace_root: Optional[str] = None):
        """
        Initialize LLM client.

        Args:
            config: atloop configuration
            workspace_root: Optional workspace root path for project skills
        """
        self.config = config
        self.chat = Chat(
            base_url=config.ai.completion.api_base,
            api_key=config.ai.completion.api_key,
            model=config.ai.completion.model,
            timeout_s=120.0,
        )

        # Initialize prompt loader (default to English)
        language = getattr(config, "prompt_language", "en")
        self.prompt_loader = PromptLoader(language=language)
        logger.debug(f"[LLMClient] Initialized PromptLoader with language: {language}")

        # Initialize enhanced skill loader with multiple directories
        builtin_skills_dir = Path(__file__).parent.parent / "skills" / "builtin"
        project_dir = Path(workspace_root) if workspace_root else None
        additional_dirs = [Path(d) for d in config.skills_dirs]
        self.skill_loader = EnhancedSkillLoader(
            builtin_skills_dir=builtin_skills_dir,
            project_dir=project_dir,
            additional_dirs=additional_dirs,
        )

        # Initialize fixed system prompt (never changes - preserves cache)
        system_template = self.prompt_loader.load("system")
        tool_schema = self.generate_tool_schema()
        skills_info = self._get_skills_info()
        self.system_prompt = system_template.replace("{TOOL_SCHEMA}", tool_schema)
        if skills_info:
            self.system_prompt += f"\n\n⚠️ Available Skills:\n{skills_info}\n\n**Important**: If a task matches a Skill description, you must immediately use the 'skill' tool to load the Skill's detailed content. Skills provide professional domain knowledge and best practice guidance."
            logger.info(
                f"[LLMClient] Added {len(self.skill_loader.skills) if self.skill_loader else 0} skills to system prompt"
            )
            logger.debug(f"[LLMClient] Skills list:\n{skills_info}")
        else:
            logger.warning(
                f"[LLMClient] No skills found (skill_loader={self.skill_loader is not None})"
            )

    def generate_tool_schema(self) -> str:
        """
        Generate tool schema description for prompt.

        Automatically extracts descriptions from tool classes instead of hardcoding.

        Returns:
            Tool schema description string
        """
        tools_desc = ["Available tools:\n"]

        try:
            from atloop.runtime.sandbox_adapter import SandboxAdapter
            from atloop.tools.registry import ToolRegistry

            dummy_sandbox = SandboxAdapter(self.config.sandbox, "dummy")
            registry = ToolRegistry(dummy_sandbox, skill_loader=self.skill_loader)

            tool_descriptions = {}
            for tool_name, tool in registry.tools.items():
                tool_descriptions[tool_name] = tool.description

            logger.debug(
                f"[LLMClient] Auto-extracted descriptions for {len(tool_descriptions)} tools"
            )
        except Exception as e:
            logger.warning(
                f"[LLMClient] Failed to auto-extract tool descriptions: {e}. Using fallback."
            )
            tool_descriptions = {}

        priority_tools = ["edit_file", "append_file"]
        other_tools = sorted([t for t in VALID_TOOLS if t not in priority_tools])

        for tool in priority_tools + other_tools:
            desc = tool_descriptions.get(tool, "No description")
            tools_desc.append(f"- {tool}: {desc}")

        return "\n".join(tools_desc)

    def _get_skills_info(self) -> str:
        """
        Get skills information for system prompt (Layer 1: metadata only).

        Returns:
            Formatted string with skill descriptions, or empty string if no skills
        """
        if not self.skill_loader:
            return ""
        return self.skill_loader.get_descriptions()

    def get_skill_content(self, skill_name: str) -> Optional[str]:
        """
        Get full skill content (Layer 2: full SKILL.md body).

        This is called when the 'skill' tool is used. The content is returned
        as a tool result (user message), preserving cache.

        Args:
            skill_name: Skill name

        Returns:
            Full skill content, or None if skill not found
        """
        if not self.skill_loader:
            return None
        return self.skill_loader.get_skill_content(skill_name)

    def load_prompt_template(self, template_name: str) -> str:
        """
        Load prompt template using PromptLoader.

        Args:
            template_name: Template name (system, developer)

        Returns:
            Template content
        """
        logger.debug(f"[LLMClient] Loading prompt template: {template_name}")
        return self.prompt_loader.load(template_name)

    def build_user_message(
        self,
        goal: str,
        constraints: List[str],
        budget: Dict[str, int],
        state_summary: Optional[str] = None,
        project_profile: Optional[str] = None,
        relevant_files: Optional[str] = None,
        recent_error: Optional[str] = None,
        current_diff: Optional[str] = None,
        test_results: Optional[str] = None,
        verification_success: Optional[bool] = None,
    ) -> str:
        """
        Build user message from context (append-only mode for cache optimization).

        This method builds a user message that will be appended to the conversation history.
        The system prompt is fixed and never changes, preserving LLM cache.

        Args:
            goal: Task goal
            constraints: Task constraints
            budget: Budget dictionary
            state_summary: State summary
            project_profile: Project profile
            relevant_files: Relevant file snippets
            recent_error: Recent error
            current_diff: Current diff
            test_results: Test results
            verification_success: Verification success status

        Returns:
            User message string (to be appended to history)
        """
        developer_prompt = self.load_prompt_template("developer")

        test_results_section = ""
        if test_results:
            if verification_success is True:
                test_status = "✅ **Tests Passed**"
                # Guide LLM to make correct decision when verification passes
                completion_reminder = """
🚨 **DECISION REQUIRED**: Tests have PASSED. You must now decide:

1. **If task goal is achieved**: Set stop_reason="done" immediately. Do not use "continue".
2. **If task goal is NOT yet achieved**: Set stop_reason="continue" and explain what remains.

**Key principle**: When verification passes AND goal is achieved, the task is complete. Use stop_reason="done" to signal completion.
"""
            elif verification_success is False:
                test_status = "❌ **Tests Failed**"
                completion_reminder = ""
            else:
                test_status = "⚠️ **Test Status Unknown**"
                completion_reminder = ""

            test_results_section = f"""
### Latest Test/Verification Results
{test_status}

{test_results}
{completion_reminder}
"""

        logger.debug(
            f"[LLMClient] build_user_message: state_summary length={len(state_summary) if state_summary else 0}"
        )

        replacements = {
            "{GOAL}": goal,
            "{CONSTRAINTS}": "\n".join(f"- {c}" for c in constraints) if constraints else "None",
            "{MAX_LLM_CALLS}": str(budget.get("max_llm_calls", 30)),
            "{MAX_TOOL_CALLS}": str(budget.get("max_tool_calls", 200)),
            "{MAX_WALL_TIME_SEC}": str(budget.get("max_wall_time_sec", 1800)),
            "{STATE_SUMMARY}": state_summary or "Initial state",
            "{PROJECT_PROFILE}": project_profile or "Not identified",
            "{RELEVANT_FILES}": relevant_files or "None",
            "{RECENT_ERROR}": recent_error or "None",
            "{CURRENT_DIFF}": current_diff or "No changes",
            "{TEST_RESULTS}": test_results_section,
        }

        for placeholder, value in replacements.items():
            if placeholder == "{STATE_SUMMARY}":
                logger.debug(
                    f"[LLMClient] Replacing {{STATE_SUMMARY}}: length={len(str(value))}, preview={str(value)[:100] if value else 'None'}..."
                )
            developer_prompt = developer_prompt.replace(placeholder, str(value))

        if "{STATE_SUMMARY}" in developer_prompt:
            logger.error("[LLMClient] Error: {STATE_SUMMARY} placeholder was not replaced!")
        else:
            logger.debug("[LLMClient] {STATE_SUMMARY} placeholder successfully replaced")

        return developer_prompt

    def build_prompt(
        self,
        goal: str,
        constraints: List[str],
        budget: Dict[str, int],
        state_summary: Optional[str] = None,
        project_profile: Optional[str] = None,
        relevant_files: Optional[str] = None,
        recent_error: Optional[str] = None,
        current_diff: Optional[str] = None,
        test_results: Optional[str] = None,
        verification_success: Optional[bool] = None,
    ) -> str:
        """
        Build complete prompt from templates (DEPRECATED - for backward compatibility).

        This method is kept for backward compatibility but should be replaced with
        build_user_message() for cache optimization.

        Args:
            goal: Task goal
            constraints: Task constraints
            budget: Budget dictionary
            state_summary: State summary
            project_profile: Project profile
            relevant_files: Relevant file snippets
            recent_error: Recent error
            current_diff: Current diff
            test_results: Test results
            verification_success: Verification success status

        Returns:
            Complete prompt string
        """
        user_message = self.build_user_message(
            goal=goal,
            constraints=constraints,
            budget=budget,
            state_summary=state_summary,
            project_profile=project_profile,
            relevant_files=relevant_files,
            recent_error=recent_error,
            current_diff=current_diff,
            test_results=test_results,
            verification_success=verification_success,
        )
        return f"{self.system_prompt}\n\n{user_message}"

    def plan_and_act(
        self,
        user_message: str,
        max_retries: int = 2,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[ActionJSON], Optional[str], Dict[str, Any], Optional[str], Dict[str, str]]:
        """
        Call LLM to plan and generate actions.

        Memory-only mode (no ChatHistory):
        - Fixed system prompt (set once, never changes - preserves cache)
        - Each call is independent with full context in user_message
        - All history is managed through Memory, not conversation history
        - Uses lexilux 2.0.0 stream() for ensuring complete responses

        Args:
            user_message: Required user message content containing all context (including memory summary)
            max_retries: Maximum retry attempts if JSON parsing fails
            stream_callback: Optional callback function to receive streaming output chunks

        Returns:
            Tuple of (ActionJSON or None, error_message, usage_info, full_output_text, file_contents_dict)
            file_contents_dict maps placeholder names to actual file content
        """
        if not user_message or not user_message.strip():
            raise ValueError("user_message is required and cannot be empty (no history mode)")

        usage_info = {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0}
        full_output = ""
        error = None

        self._log_prompt_size(user_message)

        for attempt in range(max_retries + 1):
            try:
                current_message = self._build_retry_message(user_message, attempt, error)
                self._print_streaming_status(stream_callback)

                chat_params = ChatParams(
                    temperature=0.3,
                    max_tokens=self.config.ai.performance.max_tokens_output,
                )

                initial_result = self._stream_initial_response(
                    current_message, chat_params, stream_callback
                )

                result = self._handle_truncation(initial_result, current_message, stream_callback)

                usage_info["total_tokens"] = result.usage.total_tokens
                usage_info["input_tokens"] = result.usage.input_tokens
                usage_info["output_tokens"] = result.usage.output_tokens
                full_output = result.text

                self._log_final_output(full_output, initial_result)

                action_json, error, file_contents = parse_action_json(full_output)
                self._log_file_contents_extraction(file_contents, action_json, full_output)

                if action_json:
                    return action_json, None, usage_info, full_output, file_contents
                else:
                    if attempt < max_retries:
                        continue
                    else:
                        return (
                            None,
                            f"Failed to parse Action JSON after {max_retries + 1} attempts: {error}",
                            usage_info,
                            full_output,
                            {},
                        )

            except Exception as e:
                error_str = str(e)
                if "400" in error_str and "Bad Request" in error_str:
                    logger.warning(
                        f"[LLMClient] 400 Bad Request on attempt {attempt + 1}/{max_retries + 1}. "
                        f"This may indicate the prompt is too large. Error: {error_str[:200]}"
                    )
                if attempt < max_retries:
                    continue
                return None, f"LLM call failed: {e}", usage_info, full_output, {}

        return None, "Max retries exceeded", usage_info, full_output, {}

    def _log_prompt_size(self, user_message: str) -> None:
        """Log prompt size for monitoring."""
        system_chars = len(self.system_prompt) if self.system_prompt else 0
        user_chars = len(user_message)
        total_with_system = user_chars + system_chars
        logger.info(
            f"[LLMClient] Prompt size estimate: ~{total_with_system} characters (~{total_with_system // 4} tokens) "
            f"(user_message: {user_chars} chars, system: {system_chars} chars)"
        )

    def _build_retry_message(self, user_message: str, attempt: int, error: Optional[str]) -> str:
        """Build message for retry attempt with error correction if needed."""
        if attempt > 0 and error:
            error_correction = f"""

[IMPORTANT] JSON parsing failed - please fix the following issue:

Error details: {error}

Please ensure your response is valid JSON format with the following required fields:
- "actions": array containing tool call objects
- "stop_reason": string, value must be "continue", "done", or "fail"

Each action must contain:
- "tool": tool name ("run" or "write_file")
- "args": parameter object

Example format:
{{
  "actions": [
    {{"tool": "run", "args": {{"cmd": "command"}}}},
    {{"tool": "write_file", "args": {{"path": "file.py", "content": "..."}}}}
  ],
  "stop_reason": "continue"
}}

Please output only valid JSON, do not add any other text, comments, or explanations."""
            return user_message + error_correction
        return user_message

    def _print_streaming_status(self, stream_callback: Optional[Callable[[str], None]]) -> None:
        """Print streaming status message."""
        if stream_callback:
            print("    [Streaming] ", end="", flush=True)
        else:
            print("    [Generating...] ", end="", flush=True)

    def _stream_initial_response(
        self,
        current_message: str,
        chat_params: ChatParams,
        stream_callback: Optional[Callable[[str], None]],
    ) -> ChatResult:
        """Stream initial LLM response and return result."""
        stream_iterator = self.chat.stream(
            current_message,
            system=self.system_prompt,
            include_usage=True,
            params=chat_params,
        )

        chunk_count = 0
        total_delta_length = 0
        try:
            for chunk in stream_iterator:
                chunk_count += 1
                if chunk.delta:
                    total_delta_length += len(chunk.delta)
                    if stream_callback:
                        print(chunk.delta, end="", flush=True)
                        stream_callback(chunk.delta)
                if chunk.done:
                    break
        except Exception as stream_error:
            logger.error(f"[LLMClient] Error during streaming: {stream_error}")
            logger.debug(f"[LLMClient] Exception traceback: {traceback.format_exc()}")

        logger.debug(
            f"[LLMClient] Streaming stats: {chunk_count} chunks, total delta length: {total_delta_length} chars"
        )

        if stream_callback:
            print()
        else:
            print("Done")

        initial_result = stream_iterator.result.to_chat_result()

        logger.info(
            f"[LLMClient] Initial streaming result: finish_reason={initial_result.finish_reason}, "
            f"length={len(initial_result.text)} chars, chunks={chunk_count}, "
            f"delta_total_length={total_delta_length}"
        )

        if len(initial_result.text) == 0:
            logger.error(
                f"[LLMClient] Critical error: Initial result text is empty! "
                f"chunks={chunk_count}, delta_total_length={total_delta_length}"
            )
        elif len(initial_result.text) != total_delta_length:
            logger.warning(
                f"[LLMClient] Warning: Initial result length ({len(initial_result.text)}) "
                f"does not match delta total length ({total_delta_length})!"
            )
        else:
            preview = initial_result.text[:100].replace("\n", "\\n")
            logger.debug(f"[LLMClient] Initial result preview: {preview}...")

        return initial_result

    def _handle_truncation(
        self,
        initial_result: ChatResult,
        current_message: str,
        stream_callback: Optional[Callable[[str], None]],
    ) -> ChatResult:
        """Handle response truncation by continuing generation."""
        if initial_result.finish_reason == "length":
            max_continue_attempts = 5
            if stream_callback:
                print("    [Truncation detected, continuing generation...] ", end="", flush=True)
            try:
                result = self._continue_with_streaming(
                    self.chat,
                    initial_result,
                    max_continue_attempts,
                    original_user_message=current_message,
                    stream_callback=stream_callback,
                )
                if stream_callback:
                    print()
                logger.info(
                    f"[LLMClient] Continue generation successful, final result length: {len(result.text)} chars"
                )
            except Exception as continue_error:
                logger.error(f"[LLMClient] Error during continue generation: {continue_error}")
                logger.warning(
                    f"[LLMClient] Using initial result (may be incomplete), length: {len(initial_result.text)} chars"
                )
                result = initial_result
                placeholders_in_initial = re.findall(
                    r"---\(FILE_CONTENT_#\d+\)---", initial_result.text
                )
                if placeholders_in_initial:
                    logger.warning(
                        f"[LLMClient] Initial result contains placeholders {placeholders_in_initial}, "
                        f"but file content may be incomplete due to continue failure!"
                    )
        else:
            result = initial_result

        return result

    def _log_final_output(self, full_output: str, initial_result: ChatResult) -> None:
        """Log final output statistics."""
        logger.info(
            f"[LLMClient] Final full_output length: {len(full_output)} chars, "
            f"finish_reason={initial_result.finish_reason}"
        )

        if len(full_output) == 0:
            logger.error(
                f"[LLMClient] Critical error: Final full_output is empty! "
                f"Initial result length: {len(initial_result.text)} chars"
            )
        elif len(full_output) < len(initial_result.text):
            logger.warning(
                f"[LLMClient] Warning: Final full_output ({len(full_output)} chars) "
                f"is shorter than initial result ({len(initial_result.text)} chars)!"
            )

        if initial_result.finish_reason == "length":
            logger.info(
                f"[LLMClient] Continued after truncation, final full_output length: {len(full_output)} chars"
            )
            placeholders_found = re.findall(r"---\(FILE_CONTENT_#\d+\)---", full_output)
            logger.info(f"[LLMClient] Found FILE_CONTENT placeholders: {placeholders_found}")

    def _log_file_contents_extraction(
        self,
        file_contents: Dict[str, str],
        action_json: Optional[ActionJSON],
        full_output: str,
    ) -> None:
        """Log file contents extraction results.

        File contents (---(FILE_CONTENT_#N)--- blocks) are only expected when the LLM
        uses write_file/append_file/edit_file tools with FILE_CONTENT_#N placeholders.
        For run/read_file/etc. actions, empty file_contents is normal - not a warning.
        """
        # Collect placeholders that file-writing actions expect
        expected_placeholders = []
        if action_json:
            for action in action_json.actions:
                if action.get("tool") in ["write_file", "append_file", "edit_file"]:
                    content = action.get("args", {}).get("content", "")
                    if isinstance(content, str) and content.startswith("FILE_CONTENT_#"):
                        expected_placeholders.append(content)

        if file_contents:
            logger.info(
                f"[LLMClient] Extracted {len(file_contents)} file content placeholders: {list(file_contents.keys())}"
            )
            for placeholder, content in file_contents.items():
                logger.debug(f"[LLMClient] {placeholder}: {len(content)} chars")
            # Check if any expected placeholders are missing
            missing = [p for p in expected_placeholders if p not in file_contents]
            if missing:
                logger.warning(
                    f"[LLMClient] Actions reference placeholders {missing} "
                    f"but corresponding ---(FILE_CONTENT_#N)--- blocks not found in LLM output!"
                )
        elif expected_placeholders:
            # File-writing actions use placeholders but we extracted nothing - LLM didn't provide content blocks
            logger.warning(
                f"[LLMClient] Actions reference placeholders {expected_placeholders} "
                f"but no ---(FILE_CONTENT_#N)--- blocks found in LLM output! "
                f"full_output length: {len(full_output)}"
            )
        # else: No file-writing actions with placeholders (e.g., only run/read_file) -
        # empty file_contents is expected, no need to log

    def _continue_with_streaming(
        self,
        chat: Chat,
        initial_result: ChatResult,
        max_continues: int,
        original_user_message: str,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> ChatResult:
        """
        Continue generation with streaming output when response is truncated.

        Simple approach: construct a one-round history (user prompt + AI response),
        then use a continue prompt to ask LLM to continue output.

        Args:
            chat: Chat client instance
            initial_result: Initial result (finish_reason == "length")
            max_continues: Maximum number of continuation attempts
            original_user_message: Original user message with full context
            stream_callback: Optional callback function to receive streaming output chunks

        Returns:
            Merged complete result
        """
        start_time = time.time()
        continue_prompt = (
            "Your output was truncated. Please continue outputting the remaining content."
        )

        all_results = [initial_result]
        current_result = initial_result
        continue_count = 0
        accumulated_text = initial_result.text

        logger.info(
            f"[LLMClient] Starting streaming continue generation (max {max_continues} attempts)..."
        )

        while current_result.finish_reason == "length" and continue_count < max_continues:
            continue_count += 1
            logger.info(f"[LLMClient] Starting continue generation attempt {continue_count}...")

            if stream_callback:
                print(
                    f"\n    [Continue generation {continue_count}/{max_continues}] ",
                    end="",
                    flush=True,
                )

            continue_history = ChatHistory()
            continue_history.add_user(original_user_message)
            continue_history.add_assistant(accumulated_text)
            continue_history.add_user(continue_prompt)

            chat_params = ChatParams(
                temperature=0.3,
                max_tokens=self.config.ai.performance.max_tokens_output,
            )

            try:
                continue_stream = chat.stream_with_history(
                    continue_history,
                    message=None,
                    include_usage=True,
                    params=chat_params,
                )

                for chunk in continue_stream:
                    if chunk.delta:
                        if stream_callback:
                            print(chunk.delta, end="", flush=True)
                            stream_callback(chunk.delta)
                    if chunk.done:
                        break

                continue_result = continue_stream.result.to_chat_result()
                all_results.append(continue_result)
                current_result = continue_result
                accumulated_text += continue_result.text

                logger.info(
                    f"[LLMClient] Continue generation attempt {continue_count} completed, "
                    f"length: {len(continue_result.text)} chars, "
                    f"finish_reason: {continue_result.finish_reason}, "
                    f"accumulated text length: {len(accumulated_text)} chars"
                )

                placeholders_in_continue = re.findall(
                    r"---\(FILE_CONTENT_#\d+\)---", continue_result.text
                )
                if placeholders_in_continue:
                    logger.info(
                        f"[LLMClient] Continue result contains placeholders: {placeholders_in_continue}"
                    )

                partial_pattern = r"---\(FILE_CONTENT_#\d+\)?---?"
                partial_matches = re.findall(partial_pattern, continue_result.text)
                if partial_matches:
                    logger.warning(
                        f"[LLMClient] Continue result may contain partial placeholders: {partial_matches}"
                    )

            except Exception as e:
                logger.error(
                    f"[LLMClient] Continue generation attempt {continue_count} failed: {e}"
                )
                logger.error(f"[LLMClient] Exception details: {type(e).__name__}: {e}")
                logger.debug(f"[LLMClient] Exception traceback: {traceback.format_exc()}")

                if len(all_results) > 1:
                    merged = ChatContinue.merge_results(*all_results)
                    logger.warning(
                        f"[LLMClient] Continue failed, returning partial merged result (may be incomplete), "
                        f"length: {len(merged.text)} chars, contains {len(all_results)} results"
                    )
                    placeholders_in_merged = re.findall(r"---\(FILE_CONTENT_#\d+\)---", merged.text)
                    if placeholders_in_merged:
                        logger.warning(
                            f"[LLMClient] Partial result contains placeholders {placeholders_in_merged}, "
                            f"but file content may be incomplete due to continue failure!"
                        )
                    return merged
                else:
                    logger.warning(
                        f"[LLMClient] Continue failed and only initial result available, "
                        f"returning initial result (may be incomplete), length: {len(initial_result.text)} chars"
                    )
                    return initial_result

        if len(all_results) == 1:
            full_result = all_results[0]
        else:
            full_result = ChatContinue.merge_results(*all_results)
            logger.debug(
                f"[LLMClient] Merged result: {len(all_results)} results, "
                f"total length: {len(full_result.text)} chars"
            )
            for i, r in enumerate(all_results):
                logger.debug(
                    f"[LLMClient] Result {i + 1}: {len(r.text)} chars, finish_reason: {r.finish_reason}"
                )

        elapsed_time = time.time() - start_time
        logger.info(
            f"[LLMClient] Streaming continue generation completed, elapsed: {elapsed_time:.2f}s, "
            f"total length: {len(full_result.text)} chars, {continue_count} continues"
        )

        all_placeholders = re.findall(r"---\(FILE_CONTENT_#\d+\)---", full_result.text)
        logger.info(f"[LLMClient] Merged complete text contains placeholders: {all_placeholders}")

        return full_result

    def reset_history(self):
        """
        Reset conversation history (for new task).

        NOTE: This method is kept for backward compatibility but does nothing
        since we no longer use ChatHistory. All history is managed through Memory.
        """
        pass

    def add_tool_results_to_history(
        self, actions: List[Dict[str, Any]], results: List[Dict[str, Any]]
    ):
        """
        Add tool execution results to conversation history.

        NOTE: This method is kept for backward compatibility but does nothing
        since we no longer use ChatHistory. Tool results are stored in Memory
        and included in the next memory summary.

        Args:
            actions: List of actions that were executed
            results: List of tool execution results
        """
        pass
