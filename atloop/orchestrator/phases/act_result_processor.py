"""Tool result processing utilities for ActPhase."""

import logging
from typing import Any, Dict, Optional

from atloop.config.loader import ConfigLoader
from atloop.tools.base import BaseTool
from atloop.tools.output_limit_strategy import OutputLimitStrategy


def _is_file_view_command(cmd: str) -> bool:
    """Check if command is a file view command."""
    cmd_lower = cmd.lower()
    return any(cmd in cmd_lower for cmd in ["cat ", "head ", "tail ", "sed -n"])


logger = logging.getLogger(__name__)


class ToolResultFormatter:
    """Formats tool execution results for LLM consumption."""

    @staticmethod
    def format_result_summary(tool: BaseTool, args: Dict[str, Any], result: Dict[str, Any]) -> str:
        """
        Format a tool execution result into a comprehensive summary for LLM.

        Args:
            tool: Tool instance (not tool name)
            args: Tool arguments
            result: Tool execution result

        Returns:
            Formatted result summary string
        """
        stderr = result.get("stderr", "")
        stdout = result.get("stdout", "")
        error_msg = result.get("error", "")

        parts = []
        parts.append(f"Tool: {tool.name}")
        parts.append(
            "⚠️ Important: Please carefully read the stdout and stderr content below to determine if the command succeeded."
        )

        if tool.name == "run":
            cmd = args.get("cmd", "")
            if cmd:
                parts.append(f"Command: {cmd}")

        if error_msg:
            parts.append(f"Error: {error_msg}")

        # Format stderr
        if stderr:
            stderr_preview = ToolResultFormatter._format_output(stderr, tool, args, is_stderr=True)
            parts.append(f"Stderr ({len(stderr)} chars):\n{stderr_preview}")

        # Format stdout
        if stdout:
            stdout_preview = ToolResultFormatter._format_output(stdout, tool, args, is_stderr=False)
            parts.append(f"Stdout ({len(stdout)} chars):\n{stdout_preview}")

        return "\n".join(parts)

    @staticmethod
    def _format_output(output: str, tool: BaseTool, args: Dict[str, Any], is_stderr: bool) -> str:
        """
        Format stdout or stderr output with appropriate limits.

        Uses OutputLimitStrategy to determine limits based on semantic types
        rather than tool names.

        Args:
            output: Output content
            tool: Tool instance
            args: Tool arguments
            is_stderr: Whether this is stderr (True) or stdout (False)

        Returns:
            Formatted output string
        """
        # Get limit from unified strategy system
        max_size = OutputLimitStrategy.get_limit_for_formatting(
            tool, is_stderr=is_stderr, args=args
        )

        if len(output) > max_size:
            omitted = len(output) - max_size
            return (
                output[: max_size // 2]
                + f"\n... [omitted {omitted} chars in middle] ...\n"
                + output[-max_size // 2 :]
            )
        return output


class ErrorAnalyzer:
    """Analyzes errors to provide better context and suggestions."""

    @staticmethod
    def analyze_error(tool: str, args: Dict[str, Any], result: Dict[str, Any]) -> str:
        """
        Analyze error and provide enhanced context and suggestions.

        Args:
            tool: Tool name
            args: Tool arguments
            result: Tool execution result

        Returns:
            Enhanced error message with suggestions
        """
        stderr = result.get("stderr", "")
        error_msg = result.get("error", "")
        combined_error = error_msg + "\n" + stderr if error_msg else stderr

        suggestions = []

        # Detect shell escaping issues
        if tool == "run":
            cmd = args.get("cmd", "")
            if "python3 -c" in cmd or "bash -c" in cmd:
                if "SyntaxError" in stderr or "SyntaxError" in error_msg:
                    if "invalid syntax" in stderr.lower() or "invalid syntax" in error_msg.lower():
                        suggestions.append(
                            "⚠️ **Shell Escaping Issue Detected**: "
                            "The SyntaxError is likely caused by shell escaping problems with quotes/f-strings. "
                            "**Solution**: Use `run_python_script_string` with `PYTHON_SCRIPT_#N` placeholder instead of `run` with `python3 -c`. "
                            "This avoids all shell escaping issues."
                        )

        # Detect placeholder-related errors
        if "FILE_CONTENT" in stderr or "placeholder" in stderr.lower():
            suggestions.append(
                "⚠️ **Placeholder Issue**: Check that you're using the correct placeholder type for each tool. "
                "See tool documentation for correct placeholder types."
            )

        # Detect import errors that might be path issues
        if "ImportError" in stderr or "ModuleNotFoundError" in stderr:
            if "python3" in str(args.get("cmd", "")):
                suggestions.append(
                    "💡 **Import Error**: If importing local modules, ensure the script runs from the correct directory. "
                    "Consider using `run_python_script_string` which automatically sets up the Python path."
                )

        # Combine suggestions with original error
        if suggestions:
            enhanced = "\n\n".join(suggestions) + "\n\n" + "Original Error:\n" + combined_error
            return enhanced

        return combined_error


class ErrorStateManager:
    """Manages error state updates in ActPhase."""

    @staticmethod
    def update_error_state(
        state: Any,
        tool: str,
        args: Dict[str, Any],
        result: Dict[str, Any],
        result_summary: str,
    ) -> bool:
        """
        Update error state if there's an actual error.

        Args:
            state: Agent state
            tool: Tool name
            args: Tool arguments
            result: Tool execution result
            result_summary: Formatted result summary

        Returns:
            True if error state was updated, False otherwise
        """
        stderr = result.get("stderr", "")
        error_msg = result.get("error", "")
        has_error = bool(error_msg or stderr.strip())

        if not has_error:
            # Tool succeeded - clear previous error state
            # Success typically means previous errors have been resolved or are no longer relevant
            # Historical errors are still available in tool_results_history for reference
            if state.last_error.summary:
                logger.debug(
                    f"[ErrorStateManager] Tool {tool} succeeded, clearing previous error state. "
                    f"Historical errors are still available in tool_results_history."
                )
                state.last_error.summary = ""
                state.last_error.repro_cmd = ""
                state.last_error.raw_stderr_tail = ""
            return False

        # Determine max summary size
        config = ConfigLoader.get()
        if tool == "run":
            cmd = args.get("cmd", "")
            max_summary = (
                config.limits.output.error_summary_file_view
                if _is_file_view_command(cmd)
                else config.limits.output.error_summary_normal
            )
        else:
            max_summary = config.limits.output.error_summary_normal

        # Analyze error for better context
        enhanced_error = ErrorAnalyzer.analyze_error(tool, args, result)

        # Update error state with enhanced error message
        if state.last_error.summary and state.last_error.summary.strip():
            # Append to existing error
            separator = "\n\n" + "=" * 80 + "\n"
            # Use enhanced error if available, otherwise use result_summary
            error_content = (
                enhanced_error
                if enhanced_error != (result.get("error", "") + "\n" + result.get("stderr", ""))
                else result_summary
            )
            combined = state.last_error.summary + separator + error_content
            state.last_error.summary = combined[:max_summary]
            logger.debug(
                f"[ErrorStateManager] Appended tool error to existing error summary "
                f"(total length: {len(state.last_error.summary)})"
            )
        else:
            # Set new error with enhanced message
            error_content = (
                enhanced_error
                if enhanced_error != (result.get("error", "") + "\n" + result.get("stderr", ""))
                else result_summary
            )
            state.last_error.summary = error_content[:max_summary]
            logger.debug(
                f"[ErrorStateManager] Set last_error with enhanced analysis: summary_length={len(state.last_error.summary)}"
            )

        # Update repro command and stderr tail
        if tool == "run":
            cmd = args.get("cmd", "")
            if cmd:
                state.last_error.repro_cmd = cmd

        config = ConfigLoader.get()
        stderr_tail_limit = config.limits.output.stderr_tail
        state.last_error.raw_stderr_tail = stderr[-stderr_tail_limit:] if stderr else ""

        return True


class FileChangeTracker:
    """Tracks file changes and updates state accordingly."""

    @staticmethod
    def track_file_creation(
        state: Any,
        coordinator: Any,
        file_path: str,
        file_content: str,
        modified_files: list,
    ) -> None:
        """
        Track a newly created file and update state.

        Args:
            state: Agent state
            coordinator: Workflow coordinator
            file_path: Path of the created file
            file_content: Content of the file
            modified_files: List to append file_path to
        """
        if not file_path:
            return

        modified_files.append(file_path)

        if file_path not in state.memory.created_files:
            state.memory.created_files.append(file_path)
            logger.info(
                f"[FileChangeTracker] Tracking newly created file: {file_path} "
                f"(total: {len(state.memory.created_files)})"
            )

            # Update current_diff to show file creation
            # Note: Even empty files should have a diff (showing file was created)
            diff_content = FileChangeTracker._create_file_creation_diff(
                file_path, file_content or ""
            )
            state.artifacts.current_diff = diff_content[:5000]  # Limit diff size
            logger.debug(
                f"[FileChangeTracker] Updated current_diff after file creation: {file_path}"
            )

        # CRITICAL: Store file content in modified_files_content for LLM context
        # This allows LLM to see what was written in the next round
        FileChangeTracker._update_modified_files_content(
            state, file_path, file_content, is_new=True
        )

        coordinator.state_manager.save()

    @staticmethod
    def track_file_modification(
        state: Any,
        coordinator: Any,
        file_path: str,
        file_content: str,
        modified_files: list,
        tool_name: str = "edit_file",
    ) -> None:
        """
        Track a modified file (edit_file, append_file) and update state.

        **IMPORTANT**: For edit_file and append_file, this method now reads the
        COMPLETE file content from sandbox and stores it in modified_files_content.
        This ensures the LLM can see the full file state in the next round.

        Args:
            state: Agent state
            coordinator: Workflow coordinator
            file_path: Path of the modified file
            file_content: Edit/append content (NOT the full file content for edit/append)
            modified_files: List to append file_path to
            tool_name: The tool that caused the modification ("edit_file" or "append_file")
        """
        if not file_path:
            return

        modified_files.append(file_path)

        # === NEW: Read complete file content from sandbox ===
        # For edit_file and append_file, we need to read the FULL file content
        # so the LLM can see the complete file state in the next round
        complete_file_content = file_content  # Default to provided content

        if tool_name in ("edit_file", "append_file"):
            # Read the complete file from sandbox
            complete_file_content = FileChangeTracker._read_file_from_sandbox(
                coordinator, file_path
            )
            if complete_file_content is None:
                # If read fails, fall back to provided content
                logger.warning(
                    f"[FileChangeTracker] Failed to read complete file content for {file_path}, "
                    f"using provided content instead"
                )
                complete_file_content = file_content
            else:
                logger.debug(
                    f"[FileChangeTracker] Read complete file content for {file_path} "
                    f"({len(complete_file_content)} chars)"
                )
        # === END NEW ===

        # Store file content in modified_files_content for LLM context
        FileChangeTracker._update_modified_files_content(
            state, file_path, complete_file_content, is_new=False
        )

        coordinator.state_manager.save()

    @staticmethod
    def _read_file_from_sandbox(coordinator: Any, file_path: str) -> Optional[str]:
        """
        Read complete file content from sandbox.

        Args:
            coordinator: Workflow coordinator
            file_path: Path to the file

        Returns:
            File content or None if read fails
        """
        import shlex

        try:
            path_escaped = shlex.quote(file_path)
            read_cmd = f"cat {path_escaped} 2>/dev/null"
            result = coordinator.sandbox.exec_shell(
                command=read_cmd,
                workdir="/workspace",
                timeout_seconds=30,
            )

            # Check for errors
            if result.get("stderr", "").strip():
                logger.warning(
                    f"[FileChangeTracker] Error reading file {file_path}: {result.get('stderr', '')}"
                )
                return None

            return result.get("stdout", "")
        except Exception as e:
            logger.error(f"[FileChangeTracker] Exception reading file {file_path}: {e}")
            return None

    @staticmethod
    def _update_modified_files_content(
        state: Any, file_path: str, file_content: str, is_new: bool = False
    ) -> None:
        """
        Update modified_files_content with file content.

        Args:
            state: Agent state
            file_path: Path of the file
            file_content: Content of the file
            is_new: Whether this is a newly created file
        """
        import hashlib

        # Handle None content
        if file_content is None:
            file_content = ""

        content_hash = hashlib.md5(file_content.encode()).hexdigest()[:8]

        # Check if file already exists in modified_files_content
        existing_idx = None
        for idx, record in enumerate(state.memory.modified_files_content):
            if record.get("path") == file_path:
                existing_idx = idx
                break

        file_record = {
            "path": file_path,
            "content": file_content,
            "content_hash": content_hash,
            "size": len(file_content),
            "last_modified_step": state.step,
            "is_new": is_new,
            "importance_score": FileChangeTracker._calculate_file_importance(
                file_path, file_content
            ),
        }

        if existing_idx is not None:
            # Update existing record
            state.memory.modified_files_content[existing_idx] = file_record
            logger.debug(f"[FileChangeTracker] Updated modified_files_content: {file_path}")
        else:
            # Add new record
            state.memory.modified_files_content.append(file_record)
            logger.info(
                f"[FileChangeTracker] Added to modified_files_content: {file_path} "
                f"({len(file_content)} chars, total: {len(state.memory.modified_files_content)})"
            )

        # Keep only the most recent/important files (max 10)
        if len(state.memory.modified_files_content) > 10:
            # Sort by importance and step, keep top 10
            state.memory.modified_files_content.sort(
                key=lambda x: (x.get("importance_score", 0), x.get("last_modified_step", 0)),
                reverse=True,
            )
            state.memory.modified_files_content = state.memory.modified_files_content[:10]

    @staticmethod
    def _calculate_file_importance(file_path: str, content: str) -> float:
        """
        Calculate importance score for a file.

        Args:
            file_path: Path of the file
            content: Content of the file

        Returns:
            Importance score (0.0 to 1.0)
        """
        score = 0.5  # Base score

        # Important file extensions
        important_extensions = [".py", ".js", ".ts", ".java", ".go", ".rs", ".md", ".docx", ".doc"]
        for ext in important_extensions:
            if file_path.endswith(ext):
                score += 0.2
                break

        # Important file names
        important_names = ["main", "index", "app", "config", "readme", "setup"]
        file_name_lower = file_path.lower()
        for name in important_names:
            if name in file_name_lower:
                score += 0.1
                break

        # Larger files are potentially more important
        if len(content) > 1000:
            score += 0.1
        if len(content) > 5000:
            score += 0.1

        return min(score, 1.0)

    @staticmethod
    def _create_file_creation_diff(file_path: str, file_content: str) -> str:
        """
        Create a diff string showing file creation.

        Args:
            file_path: Path of the created file
            file_content: Content of the file

        Returns:
            Diff-formatted string
        """
        lines = file_content.splitlines()
        diff_content = f"+++ {file_path}\n@@ -0,0 +1,{len(lines)} @@\n"
        for line in lines[:50]:  # First 50 lines
            diff_content += f"+{line}\n"
        if len(lines) > 50:
            diff_content += f"... ({len(lines) - 50} more lines)\n"
        return diff_content
