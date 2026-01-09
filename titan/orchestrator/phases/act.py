"""ACT phase implementation."""

import logging
from typing import Any, Dict, List

from titan.config.limits import (
    ERROR_SUMMARY_LIMIT_FILE_VIEW,
    ERROR_SUMMARY_LIMIT_NORMAL,
    STDERR_TAIL_LIMIT,
    STDOUT_STDERR_LIMIT_FILE_VIEW,
    STDOUT_STDERR_LIMIT_NORMAL,
    STDOUT_STDERR_LIMIT_OTHER,
    is_file_view_command,
)
from titan.llm import ActionJSON
from titan.orchestrator.executor.tool_executor import ToolExecutor
from titan.orchestrator.phases.base import BasePhase, PhaseContext, PhaseResult
from titan.orchestrator.state_machine import Phase

logger = logging.getLogger(__name__)


class ActPhase(BasePhase):
    """ACT phase: Execute tool calls."""

    def __init__(self, coordinator: "WorkflowCoordinator"):
        """Initialize ACT phase."""
        super().__init__(coordinator)
        self.executor = ToolExecutor(coordinator)
        logger.debug(f"[ActPhase] Initialized with ToolExecutor")

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
                logger.warning(f"[ActPhase] No actions found, transitioning back to DISCOVER")
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
                logger.debug(f"[ActPhase] Executing action {i+1}/{len(action_json.actions)}: {tool}")

                # Execute tool via executor
                result = self.executor._execute_action(action)
                logger.debug(f"[ActPhase] Action {i+1} completed: success={result.get('success', False)}")

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
                    state.last_error.raw_stderr_tail = (
                        stderr[-STDERR_TAIL_LIMIT:] if stderr else ""
                    )
                    logger.debug(f"[ActPhase] Updated last_error: summary_length={len(state.last_error.summary)}")

                # Track modified files
                if tool == "write_file":
                    file_path = args.get("path", "")
                    if file_path:
                        modified_files.append(file_path)
                        if file_path not in state.memory.created_files:
                            state.memory.created_files.append(file_path)
                            logger.info(f"[ActPhase] Tracking newly created file: {file_path} (total: {len(state.memory.created_files)})")
                            self.coordinator.state_manager.save()

                # Update budget
                state.budget_used.tool_calls += 1
                self.coordinator.budget_manager.budget_used.tool_calls += 1
                logger.debug(f"[ActPhase] Budget updated: tool_calls={state.budget_used.tool_calls}")

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
            logger.debug(f"[ActPhase] Recorded attempt: success={success}, files={len(modified_files)}")

            # Auto-detect milestones
            if success and modified_files:
                if len(modified_files) >= 3:
                    from titan.memory.memory_manager import MemoryManager
                    milestone_content = f"Successfully modified {len(modified_files)} files: {', '.join(modified_files[:3])}"
                    if len(modified_files) > 3:
                        milestone_content += " etc"
                    MemoryManager.add_milestone(state, milestone_content)
                    self.coordinator.state_manager.save()
                    logger.debug(f"[ActPhase] Added milestone: {milestone_content}")

            # Check pending stop_reason
            pending_stop_reason = self.coordinator.job_state.shared_data.get("pending_stop_reason")
            if pending_stop_reason:
                logger.info(
                    f"[ActPhase] ACT phase detected pending_stop_reason='{pending_stop_reason}', will stop after executing actions"
                )
                del self.coordinator.job_state.shared_data["pending_stop_reason"]

                if pending_stop_reason == "done":
                    logger.info(f"[ActPhase] After executing actions, marking as DONE (Step {state.step})")
                    self.coordinator.event_logger.log_decision(
                        step=state.step,
                        stop_reason="done",
                        verification_success=state.artifacts.verification_success,
                        reason="LLM determined task is complete (all actions executed)",
                    )
                    self.coordinator.state_manager.update(phase="DONE")
                    self._transition(Phase.DONE)
                    logger.info(f"[ActPhase] Set phase=DONE, main loop should exit")
                    return PhaseResult(
                        success=True,
                        data={},
                        next_phase=Phase.DONE,
                    )
                elif pending_stop_reason == "fail":
                    logger.info(f"[ActPhase] After executing actions, marking as FAIL (Step {state.step})")
                    self.coordinator.event_logger.log_decision(
                        step=state.step,
                        stop_reason="fail",
                        verification_success=state.artifacts.verification_success,
                        reason="LLM determined task failed",
                    )
                    self.coordinator.state_manager.update(phase="FAIL")
                    self._transition(Phase.FAIL)
                    logger.info(f"[ActPhase] Set phase=FAIL, main loop should exit")
                    return PhaseResult(
                        success=False,
                        data={},
                        next_phase=Phase.FAIL,
                        error="LLM determined task failed",
                    )

            # Transition to VERIFY
            logger.debug(f"[ActPhase] Transitioning to VERIFY phase")
            self._transition(Phase.VERIFY)
            self.coordinator.state_manager.update(phase="VERIFY")
            logger.info(f"[ActPhase] Successfully transitioned to VERIFY phase")

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
