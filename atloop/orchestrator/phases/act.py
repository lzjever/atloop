"""ACT phase implementation."""

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from atloop.llm import ActionJSON, ActionJSONValidationError
from atloop.orchestrator.executor.tool_executor import ToolExecutor
from atloop.orchestrator.phases.act_result_processor import (
    ErrorStateManager,
    FileChangeTracker,
    ToolResultFormatter,
)
from atloop.orchestrator.phases.base import BasePhase, PhaseContext, PhaseResult
from atloop.orchestrator.phases.placeholder_replacer import PlaceholderReplacer
from atloop.orchestrator.phases.stop_reason_handler import StopReasonHandler
from atloop.orchestrator.state_machine import Phase

if TYPE_CHECKING:
    from atloop.orchestrator.coordinator import WorkflowCoordinator

logger = logging.getLogger(__name__)


class ActPhase(BasePhase):
    """ACT phase: Execute tool calls."""

    def __init__(self, coordinator: "WorkflowCoordinator"):
        """Initialize ACT phase."""
        super().__init__(coordinator)
        self.executor = ToolExecutor(coordinator)
        logger.debug("[ActPhase] Initialized with ToolExecutor")

    def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute ACT phase.

        Args:
            context: Phase execution context

        Returns:
            Phase execution result
        """
        logger.info(f"[ActPhase] Entering ACT phase (Step {context.step})")
        state = self.coordinator.state_manager.agent_state

        try:
            # Get actions from job_state
            # Design principle: Validate at the boundary
            # ActionJSON.from_dict() will validate the data structure
            actions_dict = self.coordinator.job_state.shared_data.get("actions")
            
            if not actions_dict:
                logger.warning("[ActPhase] No actions found, transitioning back to DISCOVER")
                self.coordinator.state_manager.update(phase="DISCOVER")
                self._transition(Phase.DISCOVER)
                return PhaseResult(
                    success=True,
                    data={},
                    next_phase=Phase.DISCOVER,
                )

            # Parse and validate ActionJSON
            # ActionJSON.from_dict() will raise ActionJSONValidationError if invalid
            try:
                action_json = ActionJSON.from_dict(actions_dict, validate=True)
                logger.debug(f"[ActPhase] Parsed and validated ActionJSON: {len(action_json.actions)} actions")
            except ActionJSONValidationError as e:
                # Clear validation error with detailed message
                logger.error(f"[ActPhase] Action JSON validation failed: {e.message}")
                state.last_error.summary = f"Invalid Action JSON: {e.message}"
                self.coordinator.state_manager.update(phase="DISCOVER")
                self._transition(Phase.DISCOVER)
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.DISCOVER,
                    error=f"Invalid Action JSON: {e.message}",
                )
            except TypeError as e:
                # Type error (e.g., not a dict)
                logger.error(f"[ActPhase] Invalid Action JSON type: {e}")
                state.last_error.summary = f"Invalid Action JSON type: {e}"
                self.coordinator.state_manager.update(phase="DISCOVER")
                self._transition(Phase.DISCOVER)
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.DISCOVER,
                    error=f"Invalid Action JSON type: {e}",
                )

            # Execute actions
            # Note: Loop intervention is now handled entirely in PlanPhase by LoopInterventionExecutor
            # ActPhase simply executes whatever actions it receives
            logger.debug(f"[ActPhase] Executing {len(action_json.actions)} actions")
            results, modified_files = self._execute_actions(action_json.actions, state)

            # Update memory and detect milestones
            success = all(r.get("ok", False) for r in results)
            self._update_memory_after_execution(state, results, modified_files, success)

            # If actions failed, let Workflow handle error recovery
            # We just return the results - Workflow will check for errors and handle recovery
            if not success:
                # Check if any result has an error that should trigger recovery
                has_errors = any(r.get("error") or r.get("stderr") for r in results)
                if has_errors:
                    # Return with error info - Workflow will classify and handle recovery
                    # Note: Detailed error information has already been set in state.last_error.summary
                    # during tool execution (see lines 217-221). PhaseResult.error is only for
                    # logging and error classification, not for updating state.
                    error_messages = [
                        r.get("error") or r.get("stderr", "")
                        for r in results
                        if r.get("error") or r.get("stderr")
                    ]
                    combined_error = "\n".join(error_messages[:3])  # Limit to first 3 errors
                    logger.warning(
                        f"[ActPhase] Actions completed with errors. "
                        f"Detailed error info already set in state.last_error.summary. "
                        f"Workflow will handle error recovery."
                    )
                    return PhaseResult(
                        success=False,
                        data={"results": results},
                        next_phase=None,  # Let Workflow decide recovery phase
                        error=combined_error,  # For logging/classification only
                        recoverable=True,  # Mark as recoverable - Workflow will verify
                        error_already_set_in_state=True,  # Phase has set detailed error in state
                    )

            # Check and apply pending stop_reason using unified handler
            pending_stop_reason = self.coordinator.job_state.shared_data.pop(
                "pending_stop_reason", None
            )
            if pending_stop_reason:
                logger.info(
                    f"[ActPhase] Applying pending stop_reason='{pending_stop_reason}' "
                    f"after actions execution (Step {state.step})"
                )
                return StopReasonHandler.apply_pending_stop_reason(
                    pending_stop_reason=pending_stop_reason,
                    step=state.step,
                    verification_success=state.artifacts.verification_success,
                    event_logger=self.coordinator.event_logger,
                    state_manager=self.coordinator.state_manager,
                    state_machine=self.coordinator.state_machine,
                )

            # Transition to VERIFY
            logger.debug("[ActPhase] Transitioning to VERIFY phase")
            self._transition(Phase.VERIFY)
            self.coordinator.state_manager.update(phase="VERIFY")
            logger.info("[ActPhase] Successfully transitioned to VERIFY phase")

            return PhaseResult(
                success=True,
                data={"results": results},
                next_phase=Phase.VERIFY,
            )

        except Exception as e:
            # Let Workflow handle the exception with unified error handling
            # Just re-raise - Workflow will catch, classify, and handle recovery
            logger.error(f"[ActPhase] ACT phase exception: {e}")
            raise  # Re-raise for Workflow to handle

    def _execute_actions(
        self, actions: List[Dict[str, Any]], state: Any
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Execute all actions and process their results.

        Design principle: Trust validated data
        - Actions have been validated by ActionJSON.from_dict()
        - We can trust the data structure and focus on execution logic
        - No defensive type checks needed here

        Args:
            actions: List of actions to execute (guaranteed to be valid by ActionJSON validation)
            state: Agent state

        Returns:
            Tuple of (results, modified_files)
        """
        # Sort actions to ensure correct execution order:
        # write_file -> append_file -> edit_file -> other operations
        # This is a defensive measure in case LLM doesn't follow ordering instructions
        sorted_actions = self._sort_actions(actions)
        if sorted_actions != actions:
            logger.info(
                f"[ActPhase] Actions were reordered for correct execution sequence. "
                f"Original order: {[a.get('tool') for a in actions]}, "
                f"Sorted order: {[a.get('tool') for a in sorted_actions]}"
            )
        
        results = []
        modified_files = []

        import time
        
        for i, action in enumerate(sorted_actions):
            logger.debug(
                f"[ActPhase] Executing action {i + 1}/{len(actions)}: {action.get('tool')}"
            )

            # Validate and execute action
            self._validate_action(action, i + 1)
            result = self._execute_single_action(action)
            results.append(result)

            # Process result: format, update error state, track files
            self._process_action_result(action, result, state, modified_files)
            
            # Record action to progress tracker
            tool = action.get("tool", "unknown")
            args = action.get("args", {})
            self.coordinator.progress_tracker.record_action(
                step=state.step,
                tool=tool,
                args=args,
                result=result,
                timestamp=time.time(),
            )

            # Update budget
            state.budget_used.tool_calls += 1
            self.coordinator.budget_manager.budget_used.tool_calls += 1
            logger.debug(
                f"[ActPhase] Budget updated: tool_calls={state.budget_used.tool_calls}"
            )
        
        # Save action history to memory for persistence
        state.memory.action_history = [
            a.to_dict() for a in self.coordinator.progress_tracker.action_history
        ]

        return results, modified_files

    def _sort_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort actions to ensure correct execution order.
        
        Required order:
        1. write_file (create new files)
        2. append_file (append to existing files)
        3. edit_file (modify existing files)
        4. All other operations (read_file, run, load_skill, etc.)
        
        Args:
            actions: List of actions to sort
            
        Returns:
            Sorted list of actions
        """
        # Define priority order (lower number = higher priority, executed first)
        tool_priority = {
            "write_file": 1,
            "append_file": 2,
            "edit_file": 3,
            # All other tools have priority 4 (executed last)
        }
        
        def get_priority(action: Dict[str, Any]) -> int:
            tool = action.get("tool", "")
            return tool_priority.get(tool, 4)
        
        # Sort by priority, maintaining relative order within same priority
        # Use stable sort to preserve order of actions with same tool type
        sorted_actions = sorted(actions, key=get_priority)
        
        return sorted_actions

    def _cache_skill_metadata(
        self, state: Any, args: Dict[str, Any], result: Dict[str, Any], tool_name: str
    ) -> None:
        """
        Cache skill metadata in memory.skill_cache.
        
        Args:
            state: Agent state
            args: Tool arguments
            result: Tool execution result
            tool_name: Tool name
        """
        if not result.get("ok"):
            return
        
        skill_name = args.get("name")
        if not skill_name:
            return
        
        meta = result.get("meta", {})
        resources = meta.get("resources", {})
        
        # Initialize skill cache entry if not exists
        if skill_name not in state.memory.skill_cache:
            state.memory.skill_cache[skill_name] = {
                "metadata": {},
                "resources": {
                    "scripts": {},
                    "references": {},
                    "assets": {},
                },
            }
        
        # Extract metadata from stdout (which contains the formatted skill content)
        # The stdout contains: # Skill: name, Description, Main Content (body), Available Resources
        stdout = result.get("stdout", "")
        
        # Parse description and body from stdout
        # Format: # Skill: name\n**Source**: ...\n\n## Description\n...\n\n## Main Content\n...\n\n
        description = ""
        body = ""
        
        if "## Description" in stdout:
            desc_start = stdout.find("## Description") + len("## Description")
            if "## Main Content" in stdout:
                desc_end = stdout.find("## Main Content")
                description = stdout[desc_start:desc_end].strip()
            else:
                description = stdout[desc_start:].strip()
        
        if "## Main Content" in stdout:
            body_start = stdout.find("## Main Content") + len("## Main Content")
            if "## Available Resources" in stdout:
                body_end = stdout.find("## Available Resources")
                body = stdout[body_start:body_end].strip()
            else:
                body = stdout[body_start:].strip()
        
        # Update metadata
        state.memory.skill_cache[skill_name]["metadata"] = {
            "name": skill_name,
            "description": description or meta.get("description", ""),
            "body": body or stdout,  # Fallback to full stdout if parsing fails
            "loaded_at_step": state.step,
        }
        
        # Store resource list for reference
        state.memory.skill_cache[skill_name]["_resource_list"] = resources
        
        logger.debug(
            f"[ActPhase] Cached skill metadata: {skill_name} (Step {state.step})"
        )

    def _cache_skill_resource(
        self, state: Any, args: Dict[str, Any], result: Dict[str, Any], tool_name: str
    ) -> None:
        """
        Cache skill resource content in memory.skill_cache.
        
        Args:
            state: Agent state
            args: Tool arguments
            result: Tool execution result
            tool_name: Tool name
        """
        if not result.get("ok"):
            return
        
        skill_name = args.get("skill_name")
        resource_type = args.get("resource_type")
        resource_name = args.get("resource_name")
        
        if not all([skill_name, resource_type, resource_name]):
            return
        
        # Get content from meta (stored by tool)
        meta = result.get("meta", {})
        content = meta.get("_content")
        
        if not content:
            logger.warning(
                f"[ActPhase] No content found in result meta for {skill_name}/{resource_type}/{resource_name}"
            )
            return
        
        # Initialize skill cache entry if not exists
        if skill_name not in state.memory.skill_cache:
            state.memory.skill_cache[skill_name] = {
                "metadata": {},
                "resources": {
                    "scripts": {},
                    "references": {},
                    "assets": {},
                },
            }
        
        # Cache resource content
        if resource_type not in state.memory.skill_cache[skill_name]["resources"]:
            state.memory.skill_cache[skill_name]["resources"][resource_type] = {}
        
        state.memory.skill_cache[skill_name]["resources"][resource_type][resource_name] = {
            "content": content,
            "loaded_at_step": state.step,
        }
        
        logger.debug(
            f"[ActPhase] Cached skill resource: {skill_name}/{resource_type}/{resource_name} "
            f"({len(content)} chars, Step {state.step})"
        )

    def _validate_action(self, action: Dict[str, Any], action_index: int) -> None:
        """
        Validate action before execution.

        Args:
            action: Action dictionary
            action_index: Index of action (for logging)
        """
        tool = action.get("tool")
        args = action.get("args", {})

        # Check for unreplaced placeholders in all tools that use placeholders
        if tool in PlaceholderReplacer.CONTENT_TOOLS:
            # Determine which field to check based on tool
            if tool in ["write_file", "append_file", "edit_file"]:
                value = args.get("content", "")
                field_name = "content"
            elif tool == "run":
                value = args.get("cmd", "")
                field_name = "cmd"
            elif tool in ["run_python_script_string", "run_shell_script_string"]:
                value = args.get("script", "")
                field_name = "script"
            else:
                value = ""
                field_name = ""

            if PlaceholderReplacer._is_valid_placeholder(value):
                logger.error(
                    f"[ActPhase] ❌ CRITICAL: {tool} action {action_index} has unreplaced placeholder "
                    f"{value} in field '{field_name}'! This indicates placeholder replacement failed in PlanPhase."
                )

    def _execute_single_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single action and return result.

        Args:
            action: Action dictionary

        Returns:
            Tool execution result
        """
        tool = action.get("tool")
        args = action.get("args", {})

        try:
            result = self.executor._execute_action(action)
            logger.debug(
                f"[ActPhase] Action completed: success={result.get('success', False)}"
            )
            return result
        except Exception as e:
            # Convert exception to error result format
            # This allows the workflow to continue processing other actions
            logger.warning(
                f"[ActPhase] Action raised exception: {e}. "
                f"Converting to error result for LLM to handle."
            )
            error_result = {
                "success": False,
                "ok": False,
                "tool": tool,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "error": str(e),
                "exit_code": 1,
            }
            if tool == "run":
                error_result["command"] = args.get("cmd", "")
            return error_result

    def _process_action_result(
        self,
        action: Dict[str, Any],
        result: Dict[str, Any],
        state: Any,
        modified_files: List[str],
    ) -> None:
        """
        Process a single action result: format, update error state, track files.

        Args:
            action: Original action dictionary
            result: Tool execution result
            state: Agent state
            modified_files: List to append modified files to
        """
        tool_name = action.get("tool")
        args = action.get("args", {})

        # Get tool instance from registry
        tool = self.coordinator.tool_runtime.registry.get(tool_name)
        if not tool:
            # Fallback: use tool name if tool instance not found
            # This should not happen in normal operation, but provides defensive handling
            logger.warning(
                f"[ActPhase] Tool instance not found for '{tool_name}', creating fallback tool"
            )
            # Create a minimal tool-like object that implements BaseTool interface
            from atloop.tools.base import BaseTool
            from atloop.tools.output_semantic_type import OutputSemanticType

            class FallbackTool(BaseTool):
                def __init__(self, name: str):
                    self._name = name

                @property
                def name(self) -> str:
                    return self._name

                @property
                def description(self) -> str:
                    return f"Fallback tool for {self._name}"

                def execute(self, args):
                    raise NotImplementedError("Fallback tool cannot execute")

                @property
                def output_semantic_type(self):
                    return OutputSemanticType.STATUS_MESSAGE

            tool = FallbackTool(tool_name)

        # Format result summary for LLM
        result_summary = ToolResultFormatter.format_result_summary(tool, args, result)

        # Update error state if there's an error
        ErrorStateManager.update_error_state(state, tool_name, args, result, result_summary)

        # Handle skill caching
        if tool_name == "load_skill":
            self._cache_skill_metadata(state, args, result, tool_name)
        elif tool_name == "load_skill_resource":
            self._cache_skill_resource(state, args, result, tool_name)

        # Track file changes - populate modified_files_content for LLM context
        if tool_name == "write_file":
            file_path = args.get("path", "")
            file_content = args.get("content", "")
            FileChangeTracker.track_file_creation(
                state, self.coordinator, file_path, file_content, modified_files
            )
        elif tool_name in ("edit_file", "append_file"):
            file_path = args.get("path", "")
            file_content = args.get("content", "")
            # For edit_file and append_file, track as modification
            # Note: The content here is the edit/append content, not the full file
            # We store it so LLM knows what was changed
            FileChangeTracker.track_file_modification(
                state, self.coordinator, file_path, file_content, modified_files
            )

    def _update_memory_after_execution(
        self,
        state: Any,
        results: List[Dict[str, Any]],
        modified_files: List[str],
        success: bool,
    ) -> None:
        """
        Update memory with execution results and detect milestones.

        Args:
            state: Agent state
            results: Tool execution results
            modified_files: List of modified files
            success: Whether all actions succeeded
        """
        # Record attempt
        state.memory.attempts.append(
            {
                "step": state.step,
                "files": modified_files,
                "success": success,
                "results": results,
            }
        )
        logger.debug(
            f"[ActPhase] Recorded attempt: success={success}, files={len(modified_files)}"
        )

        # Auto-detect milestones
        if success and modified_files and len(modified_files) >= 3:
            from atloop.memory.memory_manager import MemoryManager

            milestone_content = (
                f"Successfully modified {len(modified_files)} files: "
                f"{', '.join(modified_files[:3])}"
            )
            if len(modified_files) > 3:
                milestone_content += " etc"
            MemoryManager.add_milestone(state, milestone_content)
            self.coordinator.state_manager.save()
            logger.debug(f"[ActPhase] Added milestone: {milestone_content}")
