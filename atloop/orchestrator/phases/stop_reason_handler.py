"""Stop reason handler for unified stop_reason processing."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from atloop.llm import ActionJSON
from atloop.orchestrator.phases.base import PhaseResult
from atloop.orchestrator.state_machine import Phase

logger = logging.getLogger(__name__)


class StopReasonHandler:
    """Unified handler for stop_reason processing across phases."""

    @staticmethod
    def process_stop_reason(
        stop_reason: str,
        actions: List[Dict[str, Any]],
        action_json: ActionJSON,
        verification_success: Optional[bool],
        step: int,
        event_logger,
        state_manager,
        state_machine,
        job_state,
    ) -> Tuple[Optional[Phase], Optional[str], PhaseResult]:
        """
        Process stop_reason and determine next phase.

        Args:
            stop_reason: Stop reason from LLM ("done", "fail", "continue")
            actions: List of actions to execute
            action_json: Full ActionJSON object
            verification_success: Verification result (if available)
            step: Current step number
            event_logger: Event logger instance
            state_manager: State manager instance
            state_machine: State machine instance
            job_state: Job state instance

        Returns:
            Tuple of (next_phase, pending_stop_reason, PhaseResult)
            - next_phase: Next phase to transition to (None if immediate stop)
            - pending_stop_reason: Stop reason to apply after actions (None if immediate)
            - PhaseResult: Result for current phase
        """
        if stop_reason == "done":
            return StopReasonHandler._handle_done(
                actions,
                action_json,
                verification_success,
                step,
                event_logger,
                state_manager,
                state_machine,
                job_state,
            )
        elif stop_reason == "fail":
            return StopReasonHandler._handle_fail(
                action_json, verification_success, step, event_logger, state_manager, state_machine
            )
        else:  # continue
            return StopReasonHandler._handle_continue(
                actions,
                action_json,
                verification_success,
                step,
                event_logger,
                state_manager,
                state_machine,
                job_state,
            )

    @staticmethod
    def _handle_done(
        actions: List[Dict[str, Any]],
        action_json: ActionJSON,
        verification_success: Optional[bool],
        step: int,
        event_logger,
        state_manager,
        state_machine,
        job_state,
    ) -> Tuple[Optional[Phase], Optional[str], PhaseResult]:
        """Handle stop_reason='done'."""
        logger.info(f"[StopReasonHandler] Task done (Step {step}), actions={len(actions)}")

        if not actions:
            # No actions: stop immediately
            logger.info("[StopReasonHandler] No actions, stopping immediately")
            event_logger.log_decision(
                step=step,
                stop_reason="done",
                verification_success=verification_success,
                reason="LLM determined task is complete",
            )
            state_manager.update(phase="DONE")
            state_machine.transition(Phase.DONE)
            return (
                Phase.DONE,
                None,
                PhaseResult(success=True, data={}, next_phase=Phase.DONE),
            )
        else:
            # Has actions: execute them first, then stop
            logger.info(
                f"[StopReasonHandler] Has {len(actions)} actions, will stop after execution"
            )
            StopReasonHandler._store_actions_for_act(actions, action_json, job_state)
            job_state.shared_data["pending_stop_reason"] = "done"
            state_manager.update(phase="ACT")
            state_machine.transition(Phase.ACT)
            return (
                Phase.ACT,
                "done",
                PhaseResult(success=True, data={"actions": actions}, next_phase=Phase.ACT),
            )

    @staticmethod
    def _handle_fail(
        action_json: ActionJSON,
        verification_success: Optional[bool],
        step: int,
        event_logger,
        state_manager,
        state_machine,
    ) -> Tuple[Optional[Phase], Optional[str], PhaseResult]:
        """Handle stop_reason='fail'."""
        logger.info(f"[StopReasonHandler] Task failed (Step {step})")
        event_logger.log_decision(
            step=step,
            stop_reason="fail",
            verification_success=verification_success,
            reason="LLM determined task failed",
        )
        state_manager.update(phase="FAIL")
        state_machine.transition(Phase.FAIL)
        return (
            Phase.FAIL,
            None,
            PhaseResult(
                success=False,
                data={},
                next_phase=Phase.FAIL,
                error="LLM determined task failed",
            ),
        )

    @staticmethod
    def _handle_continue(
        actions: List[Dict[str, Any]],
        action_json: ActionJSON,
        verification_success: Optional[bool],
        step: int,
        event_logger,
        state_manager,
        state_machine,
        job_state,
    ) -> Tuple[Optional[Phase], Optional[str], PhaseResult]:
        """Handle stop_reason='continue'."""
        logger.debug(f"[StopReasonHandler] Continuing (Step {step}), actions={len(actions)}")
        event_logger.log_decision(
            step=step,
            stop_reason="continue",
            verification_success=verification_success,
            reason="LLM chose to continue execution",
        )

        if not actions:
            # No actions: go back to DISCOVER to replan
            logger.info("[StopReasonHandler] No actions, returning to DISCOVER")
            state_manager.agent_state.memory.notes.append(
                "LLM chose to continue but provided no actions, will replan"
            )
            state_manager.update(phase="DISCOVER")
            state_machine.transition(Phase.DISCOVER)
            return (
                Phase.DISCOVER,
                None,
                PhaseResult(success=True, data={}, next_phase=Phase.DISCOVER),
            )
        else:
            # Has actions: execute them
            logger.info(f"[StopReasonHandler] Has {len(actions)} actions, proceeding to ACT")
            StopReasonHandler._store_actions_for_act(actions, action_json, job_state)
            state_manager.update(phase="ACT")
            transition_result = state_machine.transition(Phase.ACT)
            if not transition_result:
                logger.error("[StopReasonHandler] State transition failed: PLAN -> ACT")
                state_manager.agent_state.last_error.summary = (
                    "State transition failed: PLAN -> ACT"
                )
                state_manager.update(phase="FAIL")
                state_machine.transition(Phase.FAIL)
                return (
                    Phase.FAIL,
                    None,
                    PhaseResult(
                        success=False,
                        data={},
                        next_phase=Phase.FAIL,
                        error="State transition failed: PLAN -> ACT",
                    ),
                )
            return (
                Phase.ACT,
                None,
                PhaseResult(success=True, data={"actions": actions}, next_phase=Phase.ACT),
            )

    @staticmethod
    def _store_actions_for_act(
        actions: List[Dict[str, Any]], action_json: ActionJSON, job_state
    ) -> None:
        """Store actions in job_state for ACT phase."""
        action_json_with_replaced = ActionJSON(
            thought_summary=action_json.thought_summary,
            plan=action_json.plan,
            actions=actions,
            stop_reason=action_json.stop_reason,
            result_message=action_json.result_message,
        )
        job_state.shared_data["actions"] = action_json_with_replaced.to_dict()
        logger.debug(f"[StopReasonHandler] Stored {len(actions)} actions for ACT phase")

    @staticmethod
    def apply_pending_stop_reason(
        pending_stop_reason: str,
        step: int,
        verification_success: Optional[bool],
        event_logger,
        state_manager,
        state_machine,
    ) -> PhaseResult:
        """
        Apply pending stop_reason after actions are executed.

        Args:
            pending_stop_reason: Pending stop reason ("done" or "fail")
            step: Current step number
            verification_success: Verification result
            event_logger: Event logger instance
            state_manager: State manager instance
            state_machine: State machine instance

        Returns:
            PhaseResult with appropriate next_phase
        """
        if pending_stop_reason == "done":
            logger.info(f"[StopReasonHandler] Applying pending stop_reason='done' (Step {step})")
            event_logger.log_decision(
                step=step,
                stop_reason="done",
                verification_success=verification_success,
                reason="LLM determined task is complete (all actions executed)",
            )
            state_manager.update(phase="DONE")
            state_machine.transition(Phase.DONE)
            return PhaseResult(success=True, data={}, next_phase=Phase.DONE)

        elif pending_stop_reason == "fail":
            logger.info(f"[StopReasonHandler] Applying pending stop_reason='fail' (Step {step})")
            event_logger.log_decision(
                step=step,
                stop_reason="fail",
                verification_success=verification_success,
                reason="LLM determined task failed",
            )
            state_manager.update(phase="FAIL")
            state_machine.transition(Phase.FAIL)
            return PhaseResult(
                success=False,
                data={},
                next_phase=Phase.FAIL,
                error="LLM determined task failed",
            )

        else:
            logger.warning(
                f"[StopReasonHandler] Unknown pending_stop_reason: {pending_stop_reason}"
            )
            # Default to continue
            return PhaseResult(success=True, data={}, next_phase=Phase.VERIFY)
