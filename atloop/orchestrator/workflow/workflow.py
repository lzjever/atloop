"""Single workflow implementation - DISCOVER -> PLAN -> ACT -> VERIFY."""

import logging
from typing import TYPE_CHECKING, Any, Dict

from atloop.orchestrator.coordinator import WorkflowCoordinator

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
                logger.error(f"[Workflow] Workflow failed: {result.error}")
                return self._failure(result.error or "Workflow failed")

            # Transition
            if result.next_phase:
                logger.debug(f"[Workflow] Transitioning to phase: {result.next_phase}")
                self.coordinator.state_machine.transition(result.next_phase)
                self.coordinator.state_manager.update(phase=result.next_phase.value)

        logger.warning(f"[Workflow] Max iterations reached: {max_iterations}")
        return self._failure("Max iterations reached")

    def _execute_phase(self, phase: Phase, step: int) -> "PhaseResult":
        """Execute a phase - single method."""
        from atloop.orchestrator.phases.base import PhaseContext, PhaseResult  # noqa: F401

        context = PhaseContext(step=step, phase=phase)
        logger.debug(f"[Workflow] Executing phase {phase} at step {step}")

        try:
            if phase == Phase.DISCOVER:
                return self.discover.execute(context)
            elif phase == Phase.PLAN:
                return self.plan.execute(context)
            elif phase == Phase.ACT:
                return self.act.execute(context)
            elif phase == Phase.VERIFY:
                return self.verify.execute(context)
            else:
                logger.error(f"[Workflow] Unknown phase: {phase}")
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.FAIL,
                    error=f"Unknown phase: {phase}",
                )
        except Exception as e:
            logger.error(f"[Workflow] Phase {phase} error: {e}")
            logger.debug(f"[Workflow] Exception details: {type(e).__name__}: {e}", exc_info=True)
            return PhaseResult(
                success=False,
                data={},
                next_phase=Phase.FAIL,
                error=str(e),
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
