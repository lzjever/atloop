"""VERIFY phase implementation."""

import logging

from atloop.config.loader import ConfigLoader
from atloop.orchestrator.phases.base import BasePhase, PhaseContext, PhaseResult
from atloop.orchestrator.state_machine import Phase
from atloop.orchestrator.verification.multi_dim_verifier import MultiDimensionVerifier

logger = logging.getLogger(__name__)


class VerifyPhase(BasePhase):
    """VERIFY phase: Run verification tests with multi-dimensional validation."""

    def __init__(self, coordinator):
        """Initialize VERIFY phase."""
        super().__init__(coordinator)
        self._multi_dim_verifier = None

    @property
    def multi_dim_verifier(self) -> MultiDimensionVerifier:
        """Get or create multi-dimensional verifier."""
        if self._multi_dim_verifier is None:
            self._multi_dim_verifier = MultiDimensionVerifier(self.coordinator.sandbox)
        return self._multi_dim_verifier

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
            # Run standard verification (tests)
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
                config = ConfigLoader.get()
                test_results_limit = config.limits.context_pack.test_results
                state.artifacts.test_results = test_output[:test_results_limit]
                logger.debug(
                    f"[VerifyPhase] Test results stored: {len(test_output)} chars (limited to {test_results_limit})"
                )

            # === NEW: Multi-dimensional verification ===
            multi_dim_result = self.multi_dim_verifier.verify(state, state.artifacts)
            logger.info(
                f"[VerifyPhase] Multi-dimensional verification: "
                f"overall={multi_dim_result.overall_success}, "
                f"confidence={multi_dim_result.completion_confidence:.2f}, "
                f"summary={multi_dim_result.get_summary()}"
            )

            # Store multi-dimensional results in artifacts for context
            state.artifacts.multi_dim_verification = {
                "overall_success": multi_dim_result.overall_success,
                "completion_confidence": multi_dim_result.completion_confidence,
                "details": multi_dim_result.details,
                "summary": multi_dim_result.get_summary(),
            }
            # === END NEW ===

            # Update last error if verification failed
            # Note: We set error info here to inform LLM in next PLAN phase about verification failure.
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
                    config = ConfigLoader.get()
                    test_results_limit = config.limits.context_pack.test_results
                    error_msg_parts.append(
                        f"\nFull test output:\n{test_output[:test_results_limit]}"
                    )

                # === NEW: Add multi-dimensional verification errors ===
                if not multi_dim_result.overall_success:
                    error_msg_parts.append(
                        f"\nMulti-dimensional verification: {multi_dim_result.get_summary()}"
                    )
                    if multi_dim_result.errors:
                        error_msg_parts.append(f"\nDetails: {'; '.join(multi_dim_result.errors[:3])}")
                # === END NEW ===

                error_summary_text = (
                    "\n".join(error_msg_parts) if error_msg_parts else "Verification failed"
                )
                config = ConfigLoader.get()
                error_summary_limit = config.limits.output.error_summary_normal
                state.last_error.summary = error_summary_text[:error_summary_limit]
                state.last_error.repro_cmd = verification_result.command
                logger.debug(
                    f"[VerifyPhase] Error state updated: summary length={len(state.last_error.summary)}"
                )

            # Store verification result
            state.artifacts.verification_success = verification_result.success
            logger.debug(
                f"[VerifyPhase] Verification success stored: {verification_result.success}"
            )

            # === NEW: Smart completion detection and fast recovery ===
            decision = self._make_completion_decision(state, multi_dim_result)

            if decision.should_stop:
                logger.info(f"[VerifyPhase] Task complete: {decision.reason}")
                # Transition to DONE
                return PhaseResult(
                    success=True,
                    data={"verification_result": verification_result},
                    next_phase=Phase.DONE,
                )
            elif decision.fast_recovery:
                # Fast recovery: Go directly to PLAN for simple errors
                logger.info(f"[VerifyPhase] Fast recovery to PLAN: {decision.reason}")
                self._transition(Phase.PLAN)
                self.coordinator.state_manager.update(phase="PLAN")
                return PhaseResult(
                    success=True,
                    data={"verification_result": verification_result},
                    next_phase=Phase.PLAN,
                )
            # === END NEW ===

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
            # Let Workflow handle the exception with unified error handling
            logger.error(f"[VerifyPhase] VERIFY phase exception: {e}")
            raise  # Re-raise for Workflow to handle

    def _make_completion_decision(
        self, state, multi_dim_result
    ):
        """
        Make intelligent decision about task completion.

        Args:
            state: Current agent state
            multi_dim_result: Multi-dimensional verification result

        Returns:
            CompletionDecision with next action
        """
        from dataclasses import dataclass

        @dataclass
        class CompletionDecision:
            should_stop: bool = False
            fast_recovery: bool = False
            reason: str = ""

        # 1. Check if LLM explicitly marked task as done
        if self.coordinator.job_state.shared_data.get("pending_stop_reason") == "done":
            return CompletionDecision(
                should_stop=True,
                reason="LLM explicitly marked task as complete"
            )

        # 2. Check multi-dimensional verification confidence
        if multi_dim_result.completion_confidence >= 0.8:
            return CompletionDecision(
                should_stop=True,
                reason=f"High completion confidence ({multi_dim_result.completion_confidence:.2f})"
            )

        # 3. Check for simple recoverable errors (fast recovery to PLAN)
        if not multi_dim_result.overall_success:
            syntax_failed = not multi_dim_result.details.get("syntax", {}).get("passed", True)
            files_missing = not multi_dim_result.details.get("files_exist", {}).get("passed", True)

            if syntax_failed or files_missing:
                # Simple errors that can be fixed quickly
                return CompletionDecision(
                    fast_recovery=True,
                    reason=f"Simple error detected (syntax={syntax_failed}, files={files_missing})"
                )

        # 4. Default: Continue normal DISCOVER cycle
        return CompletionDecision(
            should_stop=False,
            fast_recovery=False,
            reason="Continue normal cycle"
        )
