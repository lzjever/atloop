"""ACT phase implementation."""

import logging
from typing import TYPE_CHECKING

from atloop.config.limits import (
    ERROR_SUMMARY_LIMIT_FILE_VIEW,
    ERROR_SUMMARY_LIMIT_NORMAL,
    STDERR_TAIL_LIMIT,
    STDOUT_STDERR_LIMIT_FILE_VIEW,
    STDOUT_STDERR_LIMIT_NORMAL,
    STDOUT_STDERR_LIMIT_OTHER,
    is_file_view_command,
)
from atloop.llm import ActionJSON
from atloop.orchestrator.executor.tool_executor import ToolExecutor
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
            actions_dict = self.coordinator.job_state.shared_data.get("actions", {})
            logger.debug(
                f"[ActPhase] ACT phase: actions_dict keys = "
                f"{list(actions_dict.keys()) if actions_dict else 'None'}"
            )

            if not actions_dict or "actions" not in actions_dict:
                logger.warning("[ActPhase] No actions found, transitioning back to DISCOVER")
                self.coordinator.state_manager.update(phase="DISCOVER")
                self._transition(Phase.DISCOVER)
                return PhaseResult(
                    success=True,
                    data={},
                    next_phase=Phase.DISCOVER,
                )

            try:
                action_json = ActionJSON.from_dict(actions_dict)
                logger.debug(f"[ActPhase] Parsed ActionJSON: {len(action_json.actions)} actions")
            except Exception as e:
                logger.error(f"[ActPhase] Invalid Action JSON: {e}")
                state.last_error.summary = f"Invalid Action JSON: {e}"
                self.coordinator.state_manager.update(phase="DISCOVER")
                self._transition(Phase.DISCOVER)
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.DISCOVER,
                    error=f"Invalid Action JSON: {e}",
                )

            # Execute actions
            logger.debug(f"[ActPhase] Executing {len(action_json.actions)} actions")
            results = []
            modified_files = []

            for i, action in enumerate(action_json.actions):
                tool = action.get("tool")
                args = action.get("args", {})
                logger.debug(
                    f"[ActPhase] Executing action {i + 1}/{len(action_json.actions)}: {tool}"
                )

                # Execute tool via executor
                result = self.executor._execute_action(action)
                logger.debug(
                    f"[ActPhase] Action {i + 1} completed: success={result.get('success', False)}"
                )

                # Add tool name to result
                result["tool"] = tool
                if tool == "run":
                    result["command"] = args.get("cmd", "")

                results.append(result)

                # Process result for LLM
                stderr = result.get("stderr", "")
                stdout = result.get("stdout", "")
                error_msg = result.get("error", "")

                # Build comprehensive result summary
                result_parts = []
                result_parts.append(f"Tool: {tool}")
                result_parts.append(
                    "⚠️ Important: Please carefully read the stdout and stderr content below to determine if the command succeeded."
                )

                if tool == "run":
                    cmd = args.get("cmd", "")
                    if cmd:
                        result_parts.append(f"Command: {cmd}")
                        state.last_error.repro_cmd = cmd

                if error_msg:
                    result_parts.append(f"Error: {error_msg}")

                # Include FULL stderr
                if stderr:
                    if tool == "run":
                        cmd = args.get("cmd", "")
                        max_stderr = (
                            STDOUT_STDERR_LIMIT_FILE_VIEW
                            if is_file_view_command(cmd)
                            else STDOUT_STDERR_LIMIT_NORMAL
                        )
                    else:
                        max_stderr = STDOUT_STDERR_LIMIT_OTHER

                    if len(stderr) > max_stderr:
                        omitted = len(stderr) - max_stderr
                        stderr_preview = (
                            stderr[: max_stderr // 2]
                            + f"\n... [omitted {omitted} chars in middle] ...\n"
                            + stderr[-max_stderr // 2 :]
                        )
                    else:
                        stderr_preview = stderr
                    result_parts.append(f"Stderr ({len(stderr)} chars):\n{stderr_preview}")

                # Include FULL stdout
                if stdout:
                    if tool == "run":
                        cmd = args.get("cmd", "")
                        max_stdout = (
                            STDOUT_STDERR_LIMIT_FILE_VIEW
                            if is_file_view_command(cmd)
                            else STDOUT_STDERR_LIMIT_NORMAL
                        )
                    else:
                        max_stdout = STDOUT_STDERR_LIMIT_OTHER

                    if len(stdout) > max_stdout:
                        omitted = len(stdout) - max_stdout
                        stdout_preview = (
                            stdout[: max_stdout // 2]
                            + f"\n... [omitted {omitted} chars in middle] ...\n"
                            + stdout[-max_stdout // 2 :]
                        )
                    else:
                        stdout_preview = stdout
                    result_parts.append(f"Stdout ({len(stdout)} chars):\n{stdout_preview}")

                # Update last_error
                result_summary = "\n".join(result_parts)
                if result_summary:
                    if tool == "run":
                        cmd = args.get("cmd", "")
                        max_summary = (
                            ERROR_SUMMARY_LIMIT_FILE_VIEW
                            if is_file_view_command(cmd)
                            else ERROR_SUMMARY_LIMIT_NORMAL
                        )
                    else:
                        max_summary = ERROR_SUMMARY_LIMIT_NORMAL

                    state.last_error.summary = result_summary[:max_summary]
                    state.last_error.raw_stderr_tail = stderr[-STDERR_TAIL_LIMIT:] if stderr else ""
                    logger.debug(
                        f"[ActPhase] Updated last_error: summary_length={len(state.last_error.summary)}"
                    )

                # Track modified files
                if tool == "write_file":
                    file_path = args.get("path", "")
                    if file_path:
                        modified_files.append(file_path)
                        if file_path not in state.memory.created_files:
                            state.memory.created_files.append(file_path)
                            logger.info(
                                f"[ActPhase] Tracking newly created file: {file_path} (total: {len(state.memory.created_files)})"
                            )

                            # Update current_diff to show file creation
                            file_content = args.get("content", "")
                            if file_content:
                                # Create a simple diff showing file was created
                                diff_content = f"+++ {file_path}\n@@ -0,0 +1,{len(file_content.splitlines())} @@\n"
                                for line in file_content.splitlines()[:50]:  # First 50 lines
                                    diff_content += f"+{line}\n"
                                if len(file_content.splitlines()) > 50:
                                    diff_content += (
                                        f"... ({len(file_content.splitlines()) - 50} more lines)\n"
                                    )
                                state.artifacts.current_diff = diff_content[
                                    :5000
                                ]  # Limit diff size
                                logger.debug(
                                    f"[ActPhase] Updated current_diff after file creation: {file_path}"
                                )

                            self.coordinator.state_manager.save()

                # Update budget
                state.budget_used.tool_calls += 1
                self.coordinator.budget_manager.budget_used.tool_calls += 1
                logger.debug(
                    f"[ActPhase] Budget updated: tool_calls={state.budget_used.tool_calls}"
                )

            # Record attempt
            success = all(r.get("ok", False) for r in results)
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
            if success and modified_files:
                if len(modified_files) >= 3:
                    from atloop.memory.memory_manager import MemoryManager

                    milestone_content = f"Successfully modified {len(modified_files)} files: {', '.join(modified_files[:3])}"
                    if len(modified_files) > 3:
                        milestone_content += " etc"
                    MemoryManager.add_milestone(state, milestone_content)
                    self.coordinator.state_manager.save()
                    logger.debug(f"[ActPhase] Added milestone: {milestone_content}")

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
            logger.error(f"[ActPhase] ACT phase error: {e}")
            logger.debug(f"[ActPhase] Exception details: {type(e).__name__}: {e}", exc_info=True)
            state = self.coordinator.state_manager.agent_state
            state.last_error.summary = f"ACT phase error: {e}"
            self.coordinator.state_manager.update(phase="FAIL")
            self._transition(Phase.FAIL)
            return PhaseResult(
                success=False,
                data={},
                next_phase=Phase.FAIL,
                error=str(e),
            )
