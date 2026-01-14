"""Single workflow implementation - DISCOVER -> PLAN -> ACT -> VERIFY."""

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from atloop.orchestrator.coordinator import WorkflowCoordinator
from atloop.orchestrator.error_handler import ErrorCategory, ErrorClassifier, ErrorRecoveryStrategy
from atloop.output.emitter import OutputEventEmitter
from atloop.output.events import (
    BudgetUpdateEvent,
    ErrorEvent,
    PhaseTransitionEvent,
    TaskCompleteEvent,
    TaskStartEvent,
)

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

        # Get event emitter
        event_emitter = OutputEventEmitter()

        # Get config for event data
        from atloop.config.loader import ConfigLoader

        config = ConfigLoader.get()
        task_id = self.coordinator.task_spec.task_id
        start_time = datetime.now()

        # Get runs directory path
        atloop_dir = ConfigLoader.get_atloop_dir()
        runs_dir = str(atloop_dir / "runs" / task_id)

        # Get agent session ID
        session_id = getattr(self.coordinator, "agent_session_id", None)

        # Emit task start event
        event_emitter.emit(
            TaskStartEvent(
                step=0,
                task_id=task_id,
                goal=self.coordinator.task_spec.goal,
                workspace_root=self.coordinator.task_spec.workspace_root,
                model=config.ai.completion.model,
                budget={
                    "max_llm_calls": config.runtime.default_budget.max_llm_calls,
                    "max_tool_calls": config.runtime.default_budget.max_tool_calls,
                    "max_wall_time_sec": config.runtime.default_budget.max_wall_time_sec,
                },
                session_id=session_id,
                runs_dir=runs_dir,
                start_time=start_time,
            )
        )

        if not self.coordinator.initialize():
            logger.error("[Workflow] Workspace initialization failed")
            return self._failure("Workspace initialization failed")

        max_iterations = 100
        logger.debug(f"[Workflow] Max iterations: {max_iterations}")

        last_budget_update_time = datetime.now()
        previous_phase: Optional[str] = None

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

            # Emit phase transition event if phase changed
            if state.phase != previous_phase:
                # Get plan snapshot for minimal mode display
                plan_snapshot = None
                if hasattr(state, "memory") and hasattr(state.memory, "plan"):
                    plan = state.memory.plan
                    if isinstance(plan, list):
                        plan_snapshot = plan

                event_emitter.emit(
                    PhaseTransitionEvent(
                        step=state.step,
                        task_id=task_id,
                        phase=state.phase,
                        previous_phase=previous_phase,
                        details={"iteration": iteration},
                        plan_snapshot=plan_snapshot,
                    )
                )
                previous_phase = state.phase

            # Emit budget update periodically (every 5 seconds or every iteration in verbose mode)
            current_time = datetime.now()
            time_since_last_update = (current_time - last_budget_update_time).total_seconds()
            if time_since_last_update >= 5.0:  # Update every 5 seconds
                event_emitter.emit(
                    BudgetUpdateEvent(
                        step=state.step,
                        task_id=task_id,
                        llm_calls_used=state.budget_used.llm_calls,
                        llm_calls_max=config.runtime.default_budget.max_llm_calls,
                        tool_calls_used=state.budget_used.tool_calls,
                        tool_calls_max=config.runtime.default_budget.max_tool_calls,
                        wall_time_sec_used=state.budget_used.wall_time_sec,
                        wall_time_sec_max=config.runtime.default_budget.max_wall_time_sec,
                    )
                )
                last_budget_update_time = current_time

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
                success_result = self._success()
                # Emit task complete event
                end_time = datetime.now()

                # Collect file modification information
                files_created = (
                    list(state.memory.created_files) if state.memory.created_files else []
                )
                files_modified = [
                    record.get("path", "")
                    for record in state.memory.modified_files_content
                    if record.get("path") and record.get("path") not in files_created
                ]
                # Combine all file changes (created + modified)
                all_files = list(set(files_created + files_modified))

                event_emitter.emit(
                    TaskCompleteEvent(
                        step=state.step,
                        task_id=task_id,
                        status="success",
                        final_step=state.step,
                        duration_sec=int((end_time - start_time).total_seconds()),
                        budget_used={
                            "llm_calls": state.budget_used.llm_calls,
                            "tool_calls": state.budget_used.tool_calls,
                            "wall_time_sec": state.budget_used.wall_time_sec,
                        },
                        files_modified=all_files,
                        summary=success_result.get("summary"),
                        session_id=session_id,
                        runs_dir=runs_dir,
                        end_time=end_time,
                        start_time=start_time,
                    )
                )
                return success_result
            elif result.next_phase == Phase.FAIL:
                # Only fail if error is truly fatal (not recoverable)
                if result.recoverable:
                    logger.warning(
                        "[Workflow] Phase returned FAIL but marked as recoverable. "
                        "Treating as recoverable error."
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
                    failure_result = self._failure(result.error or "Workflow failed")
                    # Emit error event
                    event_emitter.emit(
                        ErrorEvent(
                            step=state.step,
                            task_id=task_id,
                            phase=state.phase,
                            error_type=type(result.error).__name__
                            if result.error
                            else "UnknownError",
                            error_message=str(result.error) if result.error else "Workflow failed",
                            error_details={"recoverable": False},
                            recoverable=False,
                        )
                    )
                    # Emit task complete event
                    end_time = datetime.now()

                    # Collect file modification information
                    files_created = (
                        list(state.memory.created_files) if state.memory.created_files else []
                    )
                    files_modified = [
                        record.get("path", "")
                        for record in state.memory.modified_files_content
                        if record.get("path") and record.get("path") not in files_created
                    ]
                    all_files = list(set(files_created + files_modified))

                    event_emitter.emit(
                        TaskCompleteEvent(
                            step=state.step,
                            task_id=task_id,
                            status="failure",
                            final_step=state.step,
                            duration_sec=int((end_time - start_time).total_seconds()),
                            budget_used={
                                "llm_calls": state.budget_used.llm_calls,
                                "tool_calls": state.budget_used.tool_calls,
                                "wall_time_sec": state.budget_used.wall_time_sec,
                            },
                            files_modified=all_files,
                            error=str(result.error) if result.error else "Workflow failed",
                            session_id=session_id,
                            runs_dir=runs_dir,
                            end_time=end_time,
                            start_time=start_time,
                        )
                    )
                    return failure_result

            # Print memory statistics if debug mode is enabled
            # Print before breakpoint so user can see stats before pausing
            from atloop.config.loader import ConfigLoader

            config = ConfigLoader.get()
            if config.debug.show_memory_diagnostics:
                self._print_memory_stats(state)
                # Save memory to JSON file after memory updates (similar to LLM I/O saving)
                self._save_memory(state)

            # Breakpoint: wait for user input if breakpoint mode is enabled
            # This happens after verbose output, so user can review stats before continuing
            if config.runtime.breakpoint and current_phase == Phase.PLAN:
                self._wait_for_breakpoint(state.step)

            # Transition
            if result.next_phase:
                logger.debug(f"[Workflow] Transitioning to phase: {result.next_phase}")
                self.coordinator.state_machine.transition(result.next_phase)
                self.coordinator.state_manager.update(phase=result.next_phase.value)

        logger.warning(f"[Workflow] Max iterations reached: {max_iterations}")
        failure_result = self._failure("Max iterations reached")
        # Emit task complete event
        state = self.coordinator.state_manager.agent_state
        end_time = datetime.now()

        # Collect file modification information
        files_created = list(state.memory.created_files) if state.memory.created_files else []
        files_modified = [
            record.get("path", "")
            for record in state.memory.modified_files_content
            if record.get("path") and record.get("path") not in files_created
        ]
        all_files = list(set(files_created + files_modified))

        event_emitter.emit(
            TaskCompleteEvent(
                step=state.step,
                task_id=task_id,
                status="failure",
                final_step=state.step,
                duration_sec=int((end_time - start_time).total_seconds()),
                budget_used={
                    "llm_calls": state.budget_used.llm_calls,
                    "tool_calls": state.budget_used.tool_calls,
                    "wall_time_sec": state.budget_used.wall_time_sec,
                },
                files_modified=all_files,
                error="Max iterations reached",
                session_id=session_id,
                runs_dir=runs_dir,
                end_time=end_time,
                start_time=start_time,
            )
        )
        return failure_result

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
                    error_category = ErrorClassifier.classify(Exception(result.error), result.error)
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
                exception_info = (
                    f"\n\n--- Unexpected Phase Exception (after tool execution) ---\n{error_msg}"
                )
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
                    "[Workflow] Treating exception as recoverable, transitioning to recovery phase"
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

        # Extract result_message from multiple sources (in order of preference)
        result_message = None

        # 1. Try job_state.shared_data["actions"] (most recent, stored when stop_reason="done")
        actions_dict = self.coordinator.job_state.shared_data.get("actions")
        if actions_dict and isinstance(actions_dict, dict):
            result_message = actions_dict.get("result_message")
            if result_message:
                logger.debug(
                    f"[Workflow] Extracted result_message from job_state.shared_data['actions']: "
                    f"{result_message[:100]}..."
                )

        # 2. Fallback: try to get from last LLM response in memory
        if not result_message and state.memory.llm_responses:
            # Search backwards through llm_responses to find the most recent result_message
            for response in reversed(state.memory.llm_responses):
                if isinstance(response, dict):
                    # Check if response has stop_reason="done" and result_message
                    if response.get("stop_reason") == "done":
                        result_message = response.get("result_message")
                        if result_message:
                            logger.debug(
                                f"[Workflow] Extracted result_message from memory.llm_responses: "
                                f"{result_message[:100]}..."
                            )
                            break

        # 3. Final fallback: check important_decisions for task completion message
        if not result_message and state.memory.important_decisions:
            # Look for decision that indicates task completion
            for decision in reversed(state.memory.important_decisions):
                if isinstance(decision, dict):
                    decision_text = decision.get("decision", "")
                    if "Task completed" in decision_text and ":" in decision_text:
                        # Extract result_message from decision text (format: "Task completed: {result_message}")
                        parts = decision_text.split(":", 1)
                        if len(parts) == 2:
                            result_message = parts[1].strip()
                            if result_message:
                                logger.debug(
                                    f"[Workflow] Extracted result_message from important_decisions: "
                                    f"{result_message[:100]}..."
                                )
                                break

        return {
            "status": "success",
            "task_id": self.coordinator.task_spec.task_id,
            "step": state.step,
            "diff": state.artifacts.current_diff,
            "test_results": state.artifacts.test_results,
            "summary": result_message,  # Include result_message as summary
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

    def _print_memory_stats(self, state: Any) -> None:
        """Print memory statistics panel if verbose mode is enabled."""
        from atloop.orchestrator.memory_stats import format_memory_stats

        stats_panel = format_memory_stats(state)
        print(stats_panel)

    def _save_memory(self, state: Any) -> None:
        """
        Save memory to JSON file for debugging.

        Args:
            state: Agent state containing memory
        """
        from atloop.config.loader import ConfigLoader

        config = ConfigLoader.get()

        if not config.debug.save_memory_dump:
            return  # Skip if not enabled

        try:
            # Get run directory from event logger
            log_dir = self.coordinator.event_logger.log_dir

            # Create debug subdirectory
            debug_dir = log_dir / "debug"
            debug_dir.mkdir(exist_ok=True)

            # Save memory as JSON
            filename = debug_dir / f"step_{state.step:03d}_memory.json"
            memory_dict = state.to_dict()
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(memory_dict, f, indent=2, ensure_ascii=False)
            logger.debug(f"[Workflow] Saved memory to {filename}")
        except Exception as e:
            logger.warning(f"[Workflow] Failed to save memory: {e}")

    def _wait_for_breakpoint(self, step: int) -> None:
        """
        Wait for user input at breakpoint.

        Args:
            step: Current step number
        """
        try:
            # Get job ID (task_id) from coordinator
            task_id = self.coordinator.task_spec.task_id
            job_id = task_id  # task_id is the directory name in runs/

            print(f"\n{'=' * 70}")
            print(f"⏸️  BREAKPOINT: Step {step} - LLM response received")
            print(f"{'=' * 70}")
            print(f"📁 Job ID: {job_id}")
            print(f"📂 Debug files: runs/{job_id}/debug/")
            print(f"{'=' * 70}")
            print("Press Enter to continue...")
            input()
            print("Continuing...\n")
        except (EOFError, KeyboardInterrupt):
            # Handle cases where stdin is not available (e.g., in tests)
            logger.warning("[Workflow] Breakpoint skipped (stdin not available)")
