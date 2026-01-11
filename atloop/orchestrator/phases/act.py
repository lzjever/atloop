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
        results = []
        modified_files = []

        for i, action in enumerate(actions):
            logger.debug(
                f"[ActPhase] Executing action {i + 1}/{len(actions)}: {action.get('tool')}"
            )

            # Validate and execute action
            self._validate_action(action, i + 1)
            result = self._execute_single_action(action)
            results.append(result)

            # Process result: format, update error state, track files
            self._process_action_result(action, result, state, modified_files)

            # Update budget
            state.budget_used.tool_calls += 1
            self.coordinator.budget_manager.budget_used.tool_calls += 1
            logger.debug(
                f"[ActPhase] Budget updated: tool_calls={state.budget_used.tool_calls}"
            )

        return results, modified_files

    def _validate_action(self, action: Dict[str, Any], action_index: int) -> None:
        """
        Validate action before execution.

        Args:
            action: Action dictionary
            action_index: Index of action (for logging)
        """
        tool = action.get("tool")
        args = action.get("args", {})

        # Check for unreplaced placeholders in file content tools
        if tool in ["write_file", "append_file", "edit_file"]:
            content = args.get("content", "")
            if isinstance(content, str) and content.startswith("FILE_CONTENT_#"):
                logger.error(
                    f"[ActPhase] ❌ CRITICAL: {tool} action {action_index} has unreplaced placeholder "
                    f"{content}! This indicates placeholder replacement failed in PlanPhase."
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
        tool = action.get("tool")
        args = action.get("args", {})

        # Format result summary for LLM
        result_summary = ToolResultFormatter.format_result_summary(tool, args, result)

        # Update error state if there's an error
        ErrorStateManager.update_error_state(state, tool, args, result, result_summary)

        # Track file changes
        if tool == "write_file":
            file_path = args.get("path", "")
            file_content = args.get("content", "")
            FileChangeTracker.track_file_creation(
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
