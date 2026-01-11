"""PLAN phase implementation."""

import logging

from atloop.config.loop_detection import InterventionLevel
from atloop.memory.summarizer import MemorySummarizer
from atloop.orchestrator.phases.base import BasePhase, PhaseContext, PhaseResult
from atloop.orchestrator.phases.placeholder_replacer import (
    PlaceholderReplacementError,
    PlaceholderReplacer,
)
from atloop.orchestrator.phases.stop_reason_handler import StopReasonHandler
from atloop.orchestrator.state_machine import Phase

logger = logging.getLogger(__name__)


class PlanPhase(BasePhase):
    """PLAN phase: Call LLM to get next actions."""

    def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute PLAN phase.

        Args:
            context: Phase execution context

        Returns:
            Phase execution result
        """
        logger.debug(f"[PlanPhase] Executing PLAN phase at step {context.step}")
        state = self.coordinator.state_manager.agent_state

        try:
            # Rebuild context pack with latest state
            logger.debug("[PlanPhase] Building context pack with latest state")
            memory_config = getattr(self.coordinator.config, "memory", None)
            if memory_config:
                memory_summary_max_length = getattr(
                    self.coordinator, "_memory_summary_max_length", memory_config.summary_max_length
                )
                logger.debug(
                    f"[PlanPhase] Using memory config: max_length={memory_summary_max_length}"
                )
            else:
                memory_summary_max_length = getattr(
                    self.coordinator, "_memory_summary_max_length", 64000
                )
                logger.debug(
                    f"[PlanPhase] Using default memory summary max length: {memory_summary_max_length}"
                )

            memory_summary = MemorySummarizer.summarize(
                state,
                max_length=memory_summary_max_length,
                task_goal=self.coordinator.task_spec.goal,
            )
            logger.debug(
                f"[PlanPhase] Memory summary length: {len(memory_summary)} chars "
                f"(max: {memory_summary_max_length})"
            )

            # === Loop Detection ===
            # Analyze progress and detect loops
            loop_analysis = self.coordinator.loop_detector.analyze(
                self.coordinator.progress_tracker
            )
            
            if loop_analysis.is_looping:
                logger.warning(
                    f"[PlanPhase] Loop detected: type={loop_analysis.loop_type.value}, "
                    f"repetitions={loop_analysis.repetition_count}, "
                    f"level={loop_analysis.intervention_level.name}"
                )
                
                # Generate intervention
                intervention = self.coordinator.loop_detector.generate_intervention(loop_analysis)
                
                # Log intervention details
                logger.info(
                    f"[PlanPhase] Loop intervention: type={loop_analysis.loop_type.value}, "
                    f"level={intervention.level.name}, evidence={loop_analysis.evidence[:2]}"
                )
                
                # Inject intervention into memory summary
                if intervention.prompt_injection:
                    memory_summary = intervention.prompt_injection + "\n\n" + memory_summary
                    logger.info(
                        f"[PlanPhase] Injected {intervention.level.name} intervention into prompt"
                    )
                
                # Handle forced strategy execution
                if intervention.level >= InterventionLevel.FORCE_STRATEGY:
                    if intervention.forced_actions:
                        logger.warning(
                            f"[PlanPhase] FORCING recovery actions due to loop: "
                            f"{len(intervention.forced_actions)} actions"
                        )
                        # Store forced actions for ACT phase
                        self.coordinator.job_state.shared_data["forced_actions"] = intervention.forced_actions
            
            # Add progress metrics to memory summary for LLM awareness
            metrics = self.coordinator.progress_tracker.get_metrics(window=10)
            if metrics.total_actions > 0:
                progress_info = (
                    f"\n## Progress Metrics (Last 10 Actions)\n"
                    f"- Files created: {metrics.files_created}\n"
                    f"- Files modified: {metrics.files_modified}\n"
                    f"- Unique actions: {metrics.unique_actions}/{metrics.total_actions}\n"
                    f"- View/Modify ratio: {metrics.view_to_modify_ratio:.1f}\n"
                    f"- Consecutive same pattern: {metrics.consecutive_same_pattern}\n"
                )
                memory_summary = memory_summary + progress_info

            # Extract keywords
            logger.debug("[PlanPhase] Extracting keywords")
            keywords = self._extract_keywords()
            logger.debug(f"[PlanPhase] Extracted {len(keywords)} keywords: {keywords[:5]}")

            # Build context pack
            logger.debug("[PlanPhase] Building context pack")
            context_pack = self.coordinator.context_builder.build(
                goal=self.coordinator.task_spec.goal,
                constraints=self.coordinator.task_spec.constraints,
                recent_error=state.last_error.summary,
                current_diff=state.artifacts.current_diff,
                test_results=state.artifacts.test_results,
                verification_success=state.artifacts.verification_success,
                memory_summary=memory_summary,
                keywords=keywords,
            )
            logger.debug(
                f"[PlanPhase] Context pack built: project_profile={context_pack.project_profile}"
            )

            # Build user message
            logger.debug("[PlanPhase] Building user message")
            user_message = self.coordinator.llm_client.build_user_message(
                goal=self.coordinator.task_spec.goal,
                constraints=self.coordinator.task_spec.constraints,
                budget=self.coordinator.task_spec.budget.to_dict(),
                state_summary=memory_summary,
                project_profile=context_pack.project_profile,
                relevant_files=context_pack.relevant_files,
                recent_error=context_pack.recent_error,
                current_diff=context_pack.current_diff,
                test_results=context_pack.test_results,
                verification_success=context_pack.verification_success,
            )
            logger.debug(f"[PlanPhase] User message built: length={len(user_message)} chars")

            # Log LLM call
            full_prompt_for_log = f"{self.coordinator.llm_client.system_prompt}\n\n{user_message}"
            self.coordinator.event_logger.log_llm_call(
                step=state.step,
                prompt=full_prompt_for_log,
                tokens_in=None,
                model=self.coordinator.config.ai.completion.model,
            )
            logger.debug("[PlanPhase] LLM call logged")

            # Call LLM
            def stream_callback(delta: str):
                pass

            logger.debug("[PlanPhase] Calling LLM")
            action_json, error, usage, full_output, file_contents = (
                self.coordinator.llm_client.plan_and_act(
                    user_message,
                    stream_callback=stream_callback,
                )
            )
            logger.debug(
                f"[PlanPhase] LLM call completed: action_json={action_json is not None}, error={error}"
            )

            # Update budget
            state.budget_used.llm_calls += 1
            self.coordinator.budget_manager.budget_used.llm_calls += 1
            logger.debug(f"[PlanPhase] Budget updated: llm_calls={state.budget_used.llm_calls}")

            # Handle LLM error
            if action_json is None:
                logger.warning(f"[PlanPhase] LLM call failed: {error}")
                # Check if it's a 400 Bad Request
                if "400" in error and "Bad Request" in error:
                    logger.warning(
                        "[PlanPhase] 400 Bad Request detected, attempting to reduce memory summary size"
                    )
                    memory_config = getattr(self.coordinator.config, "memory", None)
                    if memory_config:
                        min_length = memory_config.summary_min_effective_length
                        default_max = memory_config.summary_max_length
                    else:
                        min_length = 16000
                        default_max = 64000

                    current_max = getattr(
                        self.coordinator, "_memory_summary_max_length", default_max
                    )
                    logger.warning(
                        f"[PlanPhase] 400 Bad Request detected. "
                        f"Current memory_summary_max_length: {current_max}. "
                        f"Reducing by 20% for next attempt."
                    )
                    self.coordinator._memory_summary_max_length = max(
                        min_length, int(current_max * 0.8)
                    )
                    logger.info(
                        f"[PlanPhase] New memory_summary_max_length: "
                        f"{self.coordinator._memory_summary_max_length}"
                    )

                    if self.coordinator._memory_summary_max_length <= 20000:
                        self.coordinator.event_logger.log_llm_result(
                            step=state.step,
                            actions=[],
                            stop_reason="error",
                            error=f"{error} (attempted to reduce prompt size but still failed)",
                            llm_output=full_output,
                        )
                        self.coordinator.state_manager.update(phase="FAIL")
                        self._transition(Phase.FAIL)
                        return PhaseResult(
                            success=False,
                            data={},
                            next_phase=Phase.FAIL,
                            error=f"LLM call failed: {error} (prompt may be too large)",
                        )
                    else:
                        logger.info(
                            "[PlanPhase] Continuing to next iteration with smaller memory summary"
                        )
                        return PhaseResult(
                            success=True,
                            data={},
                            next_phase=Phase.DISCOVER,
                        )

                # For other errors, fail immediately
                self.coordinator.event_logger.log_llm_result(
                    step=state.step,
                    actions=[],
                    stop_reason="error",
                    error=error,
                    llm_output=full_output,
                )
                self.coordinator.state_manager.update(phase="FAIL")
                self._transition(Phase.FAIL)
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.FAIL,
                    error=f"LLM call failed: {error}",
                )

            # Process actions
            actions = action_json.actions
            stop_reason = action_json.stop_reason
            logger.debug(
                f"[PlanPhase] LLM response: stop_reason={stop_reason}, actions={len(actions)}"
            )

            # Replace placeholders using dedicated service
            logger.debug(
                f"[PlanPhase] Preparing to replace placeholders, file_contents keys: "
                f"{list(file_contents.keys())}"
            )
            if file_contents:
                logger.info(
                    f"[PlanPhase] Received {len(file_contents)} file content placeholders: "
                    f"{list(file_contents.keys())}"
                )
            else:
                logger.warning("[PlanPhase] No file_contents received from LLM!")

            try:
                # Use PlaceholderReplacer service for clean, testable replacement
                actions = PlaceholderReplacer.replace_and_validate(
                    actions, file_contents, strict=False
                )
                logger.info(
                    f"[PlanPhase] Successfully replaced placeholders in {len(actions)} actions"
                )
            except PlaceholderReplacementError as e:
                logger.error(
                    f"[PlanPhase] Placeholder replacement failed: {e}. "
                    f"Missing placeholders: {e.missing_placeholders}"
                )
                # Continue with actions anyway - validation will catch this later
                # This allows the workflow to continue and show the error in tool execution

            # Log LLM result
            self.coordinator.event_logger.log_llm_result(
                step=state.step,
                actions=[a.to_dict() if hasattr(a, "to_dict") else a for a in actions],
                stop_reason=stop_reason,
                tokens_out=usage.get("output_tokens") if usage else None,
                llm_output=full_output,
            )

            # Store decision in memory
            decision_record = {
                "step": state.step,
                "stop_reason": stop_reason,
                "actions_count": len(actions),
                "verification_success": state.artifacts.verification_success,
            }
            if action_json:
                decision_record["thought_summary"] = action_json.thought_summary
                decision_record["plan"] = action_json.plan
                decision_record["actions"] = [
                    a.to_dict() if hasattr(a, "to_dict") else a for a in actions
                ]
            if full_output:
                decision_record["llm_output"] = full_output
            state.memory.decisions.append(decision_record)
            logger.info(
                f"[PlanPhase] Stored decision to memory.decisions "
                f"(Step {state.step}, stop_reason={stop_reason}, "
                f"actions={len(actions)}, total decisions={len(state.memory.decisions)})"
            )

            # Store LLM response
            if action_json and full_output:
                llm_response_record = {
                    "step": state.step,
                    "thought_summary": action_json.thought_summary,
                    "plan": action_json.plan,
                    "actions": [a.to_dict() if hasattr(a, "to_dict") else a for a in actions],
                    "stop_reason": stop_reason,
                    "llm_output": full_output,
                }
                state.memory.llm_responses.append(llm_response_record)
                logger.info(
                    f"[PlanPhase] Stored LLM response to memory.llm_responses "
                    f"(total responses={len(state.memory.llm_responses)})"
                )

            # Handle stop_reason using unified handler
            next_phase, pending_stop_reason, phase_result = StopReasonHandler.process_stop_reason(
                stop_reason=stop_reason,
                actions=actions,
                action_json=action_json,
                verification_success=state.artifacts.verification_success,
                step=state.step,
                event_logger=self.coordinator.event_logger,
                state_manager=self.coordinator.state_manager,
                state_machine=self.coordinator.state_machine,
                job_state=self.coordinator.job_state,
            )

            logger.debug(
                f"[PlanPhase] Stop reason processed: stop_reason={stop_reason}, "
                f"next_phase={next_phase}, pending_stop_reason={pending_stop_reason}"
            )

            return phase_result

        except Exception as e:
            # Let Workflow handle the exception with unified error handling
            logger.error(f"[PlanPhase] PLAN phase exception: {e}")
            raise  # Re-raise for Workflow to handle

    def _extract_keywords(self) -> list[str]:
        """Extract keywords from state."""
        keywords = []
        state = self.coordinator.state_manager.agent_state

        if self.coordinator.task_spec.goal:
            keywords.extend(
                self.coordinator.indexer.extract_keywords(self.coordinator.task_spec.goal)
            )

        if state.last_error.summary:
            keywords.extend(self.coordinator.indexer.extract_keywords(state.last_error.summary))

        return keywords[:10]

