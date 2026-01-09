"""VERIFY phase implementation."""

import logging

from atloop.config.limits import ERROR_SUMMARY_LIMIT_NORMAL, TEST_RESULTS_LIMIT
from atloop.orchestrator.phases.base import BasePhase, PhaseContext, PhaseResult
from atloop.orchestrator.state_machine import Phase

logger = logging.getLogger(__name__)


class VerifyPhase(BasePhase):
    """VERIFY phase: Run verification tests."""

    def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute VERIFY phase.

        Args:
            context: Phase execution context

        Returns:
            Phase execution result
        """
        logger.debug(f"[VerifyPhase] Executing VERIFY phase at step {context.step}")
        state = self.coordinator.state_manager.agent_state

        try:
            # Run verification
            logger.debug("[VerifyPhase] Running verification")
            verification_result = self.coordinator.verifier.verify()
            logger.debug(
                f"[VerifyPhase] Verification result: success={verification_result.success}, command={verification_result.command}"
            )

            # Log verification result
            self.coordinator.event_logger.log_verification(
                step=state.step,
                success=verification_result.success,
                command=verification_result.command,
                stdout=verification_result.stdout,
                stderr=verification_result.stderr,
            )

            # Update artifacts with test results
            test_output = ""
            if verification_result.stdout:
                test_output += verification_result.stdout
            if verification_result.stderr:
                if test_output:
                    test_output += "\n\n=== STDERR ===\n"
                test_output += verification_result.stderr

            if test_output:
                state.artifacts.test_results = test_output[:TEST_RESULTS_LIMIT]
                logger.debug(
                    f"[VerifyPhase] Test results stored: {len(test_output)} chars (limited to {TEST_RESULTS_LIMIT})"
                )

            # Update last error if verification failed
            if not verification_result.success and verification_result.command:
                logger.debug("[VerifyPhase] Verification failed, updating error state")
                error_msg_parts = []
                if verification_result.error_summary:
                    error_msg_parts.append(
                        f"Verification error summary:\n{verification_result.error_summary}"
                    )

                test_output = ""
                if verification_result.stdout:
                    test_output += verification_result.stdout
                if verification_result.stderr:
                    if test_output:
                        test_output += "\n\n=== STDERR ===\n"
                    test_output += verification_result.stderr

                if test_output:
                    error_msg_parts.append(
                        f"\nFull test output:\n{test_output[:TEST_RESULTS_LIMIT]}"
                    )

                error_summary_text = (
                    "\n".join(error_msg_parts) if error_msg_parts else "Verification failed"
                )
                state.last_error.summary = error_summary_text[:ERROR_SUMMARY_LIMIT_NORMAL]
                state.last_error.repro_cmd = verification_result.command
                logger.debug(
                    f"[VerifyPhase] Error state updated: summary length={len(state.last_error.summary)}"
                )

            # Store verification result
            state.artifacts.verification_success = verification_result.success
            logger.debug(
                f"[VerifyPhase] Verification success stored: {verification_result.success}"
            )

            # Task completion detection: Check if task goal is achieved
            task_goal = self.coordinator.task_spec.goal.lower()
            if state.memory.created_files and task_goal:
                # Simple heuristic: if goal contains "write" and "code" and file exists, task might be complete
                if ("write" in task_goal or "create" in task_goal) and (
                    "code" in task_goal or "file" in task_goal or "python" in task_goal
                ):
                    logger.info(
                        f"[VerifyPhase] Task completion detected: "
                        f"goal='{self.coordinator.task_spec.goal}', "
                        f"created_files={state.memory.created_files}"
                    )
                    # Add completion hint to state for next PLAN phase
                    state.memory.notes.append(
                        f"Task completion hint: File(s) {state.memory.created_files} created. "
                        f"Task goal '{self.coordinator.task_spec.goal}' appears to be achieved. "
                        f"Consider setting stop_reason='done' if task is complete."
                    )
                    logger.info("[VerifyPhase] Added task completion hint to memory.notes")

            # Transition to DISCOVER (let LLM decide in PLAN phase)
            logger.debug("[VerifyPhase] Transitioning to DISCOVER phase")
            self._transition(Phase.DISCOVER)
            self.coordinator.state_manager.update(phase="DISCOVER")
            logger.info("[VerifyPhase] Successfully transitioned to DISCOVER phase")

            return PhaseResult(
                success=True,
                data={"verification_result": verification_result},
                next_phase=Phase.DISCOVER,
            )

        except Exception as e:
            logger.error(f"[VerifyPhase] Error: {e}")
            logger.debug(f"[VerifyPhase] Exception details: {type(e).__name__}: {e}", exc_info=True)
            state = self.coordinator.state_manager.agent_state
            state.last_error.summary = f"VERIFY phase error: {e}"
            self.coordinator.state_manager.update(phase="FAIL")
            self._transition(Phase.FAIL)
            return PhaseResult(
                success=False,
                data={},
                next_phase=Phase.FAIL,
                error=str(e),
            )
