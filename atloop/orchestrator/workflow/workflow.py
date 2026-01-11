"""Single workflow implementation - DISCOVER -> PLAN -> ACT -> VERIFY."""

import logging
from typing import TYPE_CHECKING, Any, Dict

from atloop.orchestrator.coordinator import WorkflowCoordinator
from atloop.orchestrator.error_handler import ErrorClassifier, ErrorCategory, ErrorRecoveryStrategy

if TYPE_CHECKING:
    from atloop.orchestrator.phases.base import PhaseResult
from atloop.orchestrator.phases.act import ActPhase
from atloop.orchestrator.phases.discover import DiscoverPhase
from atloop.orchestrator.phases.plan import PlanPhase
from atloop.orchestrator.phases.verify import VerifyPhase
from atloop.orchestrator.state_machine import Phase

logger = logging.getLogger(__name__)


class Workflow:
    """Single workflow: DISCOVER -> PLAN -> ACT -> VERIFY."""

    def __init__(self, coordinator: WorkflowCoordinator):
        """Initialize workflow."""
        logger.debug("[Workflow] Initializing workflow")
        self.coordinator = coordinator
        self.discover = DiscoverPhase(coordinator)
        self.plan = PlanPhase(coordinator)
        self.act = ActPhase(coordinator)
        self.verify = VerifyPhase(coordinator)
        logger.debug("[Workflow] Workflow initialized with all phases")

    def run(self) -> Dict[str, Any]:
        """Run workflow - single method."""
        logger.info("[Workflow] Starting workflow execution")

        if not self.coordinator.initialize():
            logger.error("[Workflow] Workspace initialization failed")
            return self._failure("Workspace initialization failed")

        max_iterations = 100
        logger.debug(f"[Workflow] Max iterations: {max_iterations}")

        for iteration in range(1, max_iterations + 1):
            logger.debug(f"[Workflow] Iteration {iteration}/{max_iterations}")
            state = self.coordinator.state_manager.agent_state

            # Check budget
            within_budget, budget_msg = self.coordinator.budget_manager.check_all()
            logger.debug(
                f"[Workflow] Budget check: within_budget={within_budget}, msg={budget_msg}"
            )
            if not within_budget:
                logger.warning(f"[Workflow] Budget exhausted: {budget_msg}")
                return self._failure(f"Budget exhausted: {budget_msg}")

            # Update step
            old_step = state.step
            self.coordinator.state_manager.update(step=state.step + 1)
            state = self.coordinator.state_manager.agent_state
            logger.debug(f"[Workflow] Step updated: {old_step} -> {state.step}")

            # Log state
            self.coordinator.event_logger.log_state_change(
                step=state.step,
                phase=state.phase,
            )

            # Execute phase
            current_phase = Phase.from_string(state.phase)
            logger.debug(f"[Workflow] Executing phase: {current_phase} at step {state.step}")
            result = self._execute_phase(current_phase, state.step)

            # Safety check: ensure result is not None
            if result is None:
                logger.error(
                    f"[Workflow] Phase {current_phase} returned None instead of PhaseResult"
                )
                return self._failure(f"Phase {current_phase} execution returned None")

            logger.debug(
                f"[Workflow] Phase execution result: success={result.success}, next_phase={result.next_phase}"
            )

            # Check termination
            if result.next_phase == Phase.DONE:
                logger.info(f"[Workflow] Workflow completed successfully at step {state.step}")
                return self._success()
            elif result.next_phase == Phase.FAIL:
                # Only fail if error is truly fatal (not recoverable)
                if result.recoverable:
                    logger.warning(
                        f"[Workflow] Phase returned FAIL but marked as recoverable. "
                        f"Treating as recoverable error."
                    )
                    # Treat as recoverable and transition to PLAN
                    recovery_result = self._handle_recoverable_error(
                        current_phase,
                        result.error or "Unknown error",
                        result.data,
                        error_already_set_in_state=result.error_already_set_in_state,
                    )
                    # Continue with recovery result instead
                    result = recovery_result
                else:
                    logger.error(f"[Workflow] Workflow failed with fatal error: {result.error}")
                    return self._failure(result.error or "Workflow failed")

            # Transition
            if result.next_phase:
                logger.debug(f"[Workflow] Transitioning to phase: {result.next_phase}")
                self.coordinator.state_machine.transition(result.next_phase)
                self.coordinator.state_manager.update(phase=result.next_phase.value)

        logger.warning(f"[Workflow] Max iterations reached: {max_iterations}")
        return self._failure("Max iterations reached")

    def _execute_phase(self, phase: Phase, step: int) -> "PhaseResult":
        """
        Execute a phase with unified error handling.

        This method provides centralized error handling for all phases.
        Errors are classified as recoverable or fatal, and appropriate
        recovery strategies are applied.
        """
        from atloop.orchestrator.phases.base import PhaseContext, PhaseResult  # noqa: F401

        context = PhaseContext(step=step, phase=phase)
        logger.debug(f"[Workflow] Executing phase {phase} at step {step}")

        try:
            # Execute phase - phases should focus on business logic, not error handling
            if phase == Phase.DISCOVER:
                result = self.discover.execute(context)
            elif phase == Phase.PLAN:
                result = self.plan.execute(context)
            elif phase == Phase.ACT:
                result = self.act.execute(context)
            elif phase == Phase.VERIFY:
                result = self.verify.execute(context)
            else:
                logger.error(f"[Workflow] Unknown phase: {phase}")
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.FAIL,
                    error=f"Unknown phase: {phase}",
                    recoverable=False,
                )

            # If phase returned a result with error, check if it's recoverable
            if not result.success and result.error:
                # Phase may have already classified the error
                if result.recoverable:
                    logger.warning(
                        f"[Workflow] Phase {phase} returned recoverable error: {result.error}"
                    )
                    return self._handle_recoverable_error(
                        phase,
                        result.error,
                        result.data,
                        error_already_set_in_state=result.error_already_set_in_state,
                    )
                else:
                    # Classify the error
                    error_category = ErrorClassifier.classify(
                        Exception(result.error), result.error
                    )
                    if error_category == ErrorCategory.RECOVERABLE:
                        logger.warning(
                            f"[Workflow] Classified error as recoverable: {result.error}"
                        )
                        return self._handle_recoverable_error(
                            phase,
                            result.error,
                            result.data,
                            error_already_set_in_state=result.error_already_set_in_state,
                        )
                    else:
                        logger.error(f"[Workflow] Fatal error in phase {phase}: {result.error}")
                        return result

            return result

        except Exception as e:
            # Unified exception handling for all phases
            # This handles unexpected exceptions that Phase didn't catch
            logger.error(f"[Workflow] Phase {phase} raised exception: {e}")
            logger.debug(f"[Workflow] Exception details: {type(e).__name__}: {e}", exc_info=True)

            # Classify the error
            error_category = ErrorClassifier.classify(e)
            error_msg = ErrorRecoveryStrategy.format_error_for_llm(
                e, error_category, context=f"Phase {phase.value}"
            )

            # Update state with error information
            # Since this is an unexpected exception, Phase didn't set error info
            # However, we should check if Phase had already set detailed error info
            # (e.g., ActPhase might have set tool execution errors before raising exception)
            state = self.coordinator.state_manager.agent_state
            
            # Check if Phase had already set detailed error info
            # (indicated by presence of structured markers)
            has_phase_error = bool(
                state.last_error.summary
                and any(
                    marker in state.last_error.summary
                    for marker in ["Tool:", "Command:", "Stderr (", "Stdout (", "⚠️ Important:"]
                )
            )
            
            if has_phase_error:
                # Phase had set detailed error info, append exception as additional context
                # Don't overwrite Phase's detailed information
                exception_info = f"\n\n--- Unexpected Phase Exception (after tool execution) ---\n{error_msg}"
                state.last_error.summary = (state.last_error.summary + exception_info)[:5000]
                logger.debug(
                    f"[Workflow] Appended exception info to Phase's detailed error summary "
                    f"(total length: {len(state.last_error.summary)})"
                )
                # Phase had set error info, so mark it as already set
                error_already_set_in_state = True
            else:
                # No detailed error info from Phase, set exception as the error
                state.last_error.summary = error_msg[:5000]
                logger.debug(
                    f"[Workflow] Set last_error.summary with exception error_msg "
                    f"(length: {len(error_msg[:5000])})"
                )
                error_already_set_in_state = False

            if error_category == ErrorCategory.RECOVERABLE:
                logger.warning(
                    f"[Workflow] Treating exception as recoverable, transitioning to recovery phase"
                )
                return self._handle_recoverable_error(
                    phase, error_msg, {}, error_already_set_in_state=error_already_set_in_state
                )
            else:
                logger.error(f"[Workflow] Fatal exception in phase {phase}, failing workflow")
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.FAIL,
                    error=error_msg,
                    recoverable=False,
                )

    def _handle_recoverable_error(
        self,
        current_phase: Phase,
        error_msg: str,
        error_data: Dict[str, Any],
        error_already_set_in_state: bool = False,
    ) -> "PhaseResult":
        """
        Handle a recoverable error by transitioning to appropriate recovery phase.

        Design principle: Trust Phase's state management.
        - If Phase has already set detailed error info in state.last_error.summary,
          we should NOT overwrite it with simplified error_msg.
        - PhaseResult.error is only for logging/classification, not for updating state.

        Args:
            current_phase: The phase where error occurred
            error_msg: Error message (for logging/classification only)
            error_data: Additional error data
            error_already_set_in_state: If True, Phase has already set detailed error in state

        Returns:
            PhaseResult indicating transition to recovery phase
        """
        from atloop.orchestrator.phases.base import PhaseResult  # noqa: F401

        # For recoverable errors, transition to PLAN to let LLM adjust strategy
        recovery_phase = Phase.PLAN
        logger.info(
            f"[Workflow] Recoverable error in {current_phase.value}, "
            f"transitioning to {recovery_phase.value} for LLM to adjust strategy"
        )

        # Update state only if Phase hasn't already set detailed error information
        state = self.coordinator.state_manager.agent_state
        
        if error_already_set_in_state:
            # Phase has already set detailed error info in state.last_error.summary
            # Trust Phase's state management - don't overwrite with simplified error_msg
            logger.debug(
                f"[Workflow] Phase {current_phase.value} has already set detailed error info "
                f"in state.last_error.summary (length: {len(state.last_error.summary or '')}). "
                f"Preserving it. PhaseResult.error is for logging only."
            )
        else:
            # Phase didn't set error info (e.g., unexpected exception)
            # Workflow should set it for error recovery
            if state.last_error.summary:
                # State already has some error info, append to it
                logger.debug(
                    f"[Workflow] Appending error_msg to existing error summary "
                    f"(existing length: {len(state.last_error.summary)})"
                )
                state.last_error.summary = (
                    state.last_error.summary + f"\n\n--- Workflow Error Handling ---\n{error_msg}"
                )[:5000]
            else:
                # No existing error info, set it
                state.last_error.summary = error_msg[:5000]
                logger.debug(
                    f"[Workflow] Set last_error.summary with error_msg "
                    f"(length: {len(error_msg[:5000])})"
                )

        # Transition to recovery phase
        self.coordinator.state_machine.transition(recovery_phase)
        self.coordinator.state_manager.update(phase=recovery_phase.value)

        return PhaseResult(
            success=False,  # Not successful, but recoverable
            data=error_data,
            next_phase=recovery_phase,
            error=error_msg,  # For logging/classification only
            recoverable=True,
        )

    def _success(self) -> Dict[str, Any]:
        """Generate success report."""
        state = self.coordinator.state_manager.agent_state
        logger.debug(f"[Workflow] Generating success report for step {state.step}")
        return {
            "status": "success",
            "task_id": self.coordinator.task_spec.task_id,
            "step": state.step,
            "diff": state.artifacts.current_diff,
            "test_results": state.artifacts.test_results,
            "budget_used": {
                "llm_calls": state.budget_used.llm_calls,
                "tool_calls": state.budget_used.tool_calls,
                "wall_time_sec": state.budget_used.wall_time_sec,
            },
        }

    def _failure(self, reason: str) -> Dict[str, Any]:
        """Generate failure report."""
        state = self.coordinator.state_manager.agent_state
        logger.debug(f"[Workflow] Generating failure report: {reason}")
        return {
            "status": "failure",
            "task_id": self.coordinator.task_spec.task_id,
            "step": state.step,
            "reason": reason,
            "last_error": {
                "summary": state.last_error.summary,
                "repro_cmd": state.last_error.repro_cmd,
            },
            "budget_used": {
                "llm_calls": state.budget_used.llm_calls,
                "tool_calls": state.budget_used.tool_calls,
                "wall_time_sec": state.budget_used.wall_time_sec,
            },
        }
