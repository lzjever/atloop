"""PLAN phase implementation."""

import logging
from typing import Any, Optional

from atloop.orchestrator.loop_intervention_executor import (
    InterventionAction,
    LoopInterventionExecutor,
)
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

            # Get formatted memory context using new interface
            memory_context = state.memory.get_formatted_context(
                state=state,
                task_goal=self.coordinator.task_spec.goal,
                max_length=memory_summary_max_length,
                format_options={
                    "tool_results_count": 5,
                    "steps_summary_count": 3,
                    "include_file_content": True,
                    "max_file_content_length": 20000,
                },
                tool_registry=self.coordinator.tool_runtime.registry,
            )
            logger.debug(
                f"[PlanPhase] Memory context length: {len(memory_context)} chars "
                f"(max: {memory_summary_max_length})"
            )

            # === Loop Detection and Intervention ===
            # Use centralized intervention executor for clean separation of concerns
            loop_analysis = self.coordinator.loop_detector.analyze(
                self.coordinator.progress_tracker
            )

            # Generate and execute intervention if loop detected
            intervention_result = None
            if loop_analysis.is_looping:
                intervention = self.coordinator.loop_detector.generate_intervention(loop_analysis)

                # Use centralized executor to decide action
                executor = LoopInterventionExecutor(
                    workspace_path=getattr(self.coordinator.config, "workspace_root", "/workspace")
                )
                intervention_result = executor.execute(loop_analysis, intervention)

                logger.info(
                    f"[PlanPhase] Loop intervention: type={loop_analysis.loop_type.value}, "
                    f"action={intervention_result.action.value}, "
                    f"repetitions={loop_analysis.repetition_count}"
                )

                # Handle ABORT - terminate task
                if intervention_result.should_abort:
                    logger.error(f"[PlanPhase] {intervention_result.error_message}")
                    self.coordinator.state_manager.update(phase="FAIL")
                    self._transition(Phase.FAIL)
                    return PhaseResult(
                        success=False,
                        data={},
                        next_phase=Phase.FAIL,
                        error=intervention_result.error_message,
                    )

                # Handle FORCE_RECOVERY - skip LLM, use forced actions
                if intervention_result.action == InterventionAction.FORCE_RECOVERY:
                    logger.warning(
                        f"[PlanPhase] FORCING recovery: skipping LLM, executing "
                        f"{len(intervention_result.forced_actions)} recovery actions"
                    )
                    # Store forced actions for ACT phase
                    self.coordinator.job_state.shared_data["actions"] = {
                        "actions": intervention_result.forced_actions,
                        "stop_reason": "continue",
                    }
                    # Transition directly to ACT
                    self._transition(Phase.ACT)
                    self.coordinator.state_manager.update(phase="ACT")
                    return PhaseResult(
                        success=True,
                        data={"forced_recovery": True},
                        next_phase=Phase.ACT,
                    )

                # Handle INJECT_WARNING - add to memory context
                if intervention_result.prompt_injection:
                    memory_context = intervention_result.prompt_injection + "\n\n" + memory_context
                    logger.info("[PlanPhase] Injected warning into prompt")

            # Add progress metrics to memory context for LLM awareness
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
                memory_context = memory_context + progress_info

            # Extract keywords
            logger.debug("[PlanPhase] Extracting keywords")
            keywords = self._extract_keywords()
            logger.debug(f"[PlanPhase] Extracted {len(keywords)} keywords: {keywords[:5]}")

            # Build context pack
            logger.debug("[PlanPhase] Building context pack")
            context_pack = self.coordinator.context_builder.build(
                goal=self.coordinator.task_spec.goal,
                recent_error=state.last_error.summary,
                current_diff=state.artifacts.current_diff,
                test_results=state.artifacts.test_results,
                verification_success=state.artifacts.verification_success,
                memory_summary=memory_context,  # Pass memory_context as memory_summary for backward compatibility
                keywords=keywords,
            )
            logger.debug(
                f"[PlanPhase] Context pack built: project_profile={context_pack.project_profile}"
            )

            # Build user message
            logger.debug("[PlanPhase] Building user message")
            user_message = self.coordinator.llm_client.build_user_message(
                goal=self.coordinator.task_spec.goal,
                budget=self.coordinator.task_spec.budget.to_dict(),
                memory_context=memory_context,  # Use new memory_context parameter
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

            # Save LLM input if debug mode enabled
            from atloop.config.loader import ConfigLoader

            config = ConfigLoader.get()
            if config.debug.save_llm_io:
                self._save_llm_io(state.step, user_message, None, "input")

            action_json, error, usage, full_output, file_contents = (
                self.coordinator.llm_client.plan_and_act(
                    user_message,
                    stream_callback=stream_callback,
                )
            )
            logger.debug(
                f"[PlanPhase] LLM call completed: action_json={action_json is not None}, error={error}"
            )

            # Save LLM output if debug mode enabled
            if config.debug.save_llm_io:
                self._save_llm_io(state.step, None, full_output, "output")

            # Note: Breakpoint is handled in Workflow after verbose output

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

            # Validate that run tool uses placeholders (before replacement)
            from atloop.orchestrator.phases.placeholder_info import PlaceholderInfoTracker

            is_valid, error_msg, action_index = (
                PlaceholderInfoTracker.validate_run_tool_placeholders(actions)
            )
            if not is_valid:
                logger.error(f"[PlanPhase] {error_msg}")
                state.last_error.summary = error_msg
                self.coordinator.state_manager.update(phase="DISCOVER")
                self._transition(Phase.DISCOVER)
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.DISCOVER,
                    error=error_msg,
                )

            # Validate placeholder name uniqueness within the same round
            placeholder_names = []
            for i, action in enumerate(actions):
                tool = action.get("tool", "")
                args = action.get("args", {})
                field_name, value = PlaceholderReplacer.get_placeholder_field_value(tool, args)
                if field_name and PlaceholderReplacer._is_valid_placeholder(value):
                    if value in placeholder_names:
                        error_msg = (
                            f"Duplicate placeholder name '{value}' found in action {i + 1}. "
                            f"Each placeholder must have a unique name within the same round. "
                            f"Please generate unique placeholder names based on action parameters and sequence."
                        )
                        logger.error(f"[PlanPhase] {error_msg}")
                        state.last_error.summary = error_msg
                        self.coordinator.state_manager.update(phase="DISCOVER")
                        self._transition(Phase.DISCOVER)
                        return PhaseResult(
                            success=False,
                            data={},
                            next_phase=Phase.DISCOVER,
                            error=error_msg,
                        )
                    placeholder_names.append(value)

            # Replace placeholders using dedicated service
            logger.debug(
                f"[PlanPhase] Preparing to replace placeholders, file_contents keys: "
                f"{list(file_contents.keys())}"
            )

            # Check if any actions require placeholders
            expected_placeholders = []
            for action in actions:
                tool = action.get("tool", "")
                args = action.get("args", {})
                field_name, value = PlaceholderReplacer.get_placeholder_field_value(tool, args)
                if field_name and PlaceholderReplacer._is_valid_placeholder(value):
                    expected_placeholders.append(value)

            if file_contents:
                logger.info(
                    f"[PlanPhase] Received {len(file_contents)} file content placeholders: "
                    f"{list(file_contents.keys())}"
                )
            elif expected_placeholders:
                # Actions use placeholders but we received nothing - this is a problem
                logger.warning(
                    f"[PlanPhase] No file_contents received from LLM, but actions reference "
                    f"placeholders {expected_placeholders}!"
                )
            # else: No actions require placeholders (e.g., empty actions list or only read_file) -
            # empty file_contents is expected, no need to log

            try:
                # Extract placeholder info before replacement (for memory recording)
                placeholder_info_list = PlaceholderInfoTracker.extract_placeholder_info(actions)

                # Use PlaceholderReplacer service for clean, testable replacement
                # Returns successful actions and full result metadata
                successful_actions, replacement_result = (
                    PlaceholderReplacer.replace_and_validate_with_result(
                        actions, file_contents, strict=False
                    )
                )

                # Store placeholder info in job_state for ActPhase (not in action dicts)
                # Match placeholder info to successful actions by index
                # Note: successful_actions may have different length if some were pending
                # We store info for all original actions, ActPhase will match by index
                placeholder_info_dict = {
                    i: {
                        "tool": info.tool,
                        "placeholder": info.placeholder,
                        "args": info.args,
                    }
                    for i, info in enumerate(placeholder_info_list)
                }
                self.coordinator.job_state.shared_data["placeholder_info"] = placeholder_info_dict
                logger.debug(
                    f"[PlanPhase] Stored placeholder info for {len(placeholder_info_dict)} actions"
                )
                logger.info(
                    f"[PlanPhase] Placeholder replacement: {replacement_result.replaced_count}/{replacement_result.total_count} successful. "
                    f"Pending: {len(replacement_result.pending_actions)}, "
                    f"Missing: {len(replacement_result.missing_placeholders)}, "
                    f"Type mismatches: {len(replacement_result.type_mismatches)}"
                )

                # Handle type mismatches (always an error)
                if replacement_result.type_mismatches:
                    error_msg = (
                        f"Placeholder type validation failed: {replacement_result.type_mismatches}. "
                        f"Each tool must use its correct placeholder type. "
                        f"See tool documentation for correct placeholder types."
                    )
                    logger.error(f"[PlanPhase] {error_msg}")
                    state.last_error.summary = error_msg
                    self.coordinator.state_manager.update(phase="DISCOVER")
                    self._transition(Phase.DISCOVER)
                    return PhaseResult(
                        success=False,
                        data={},
                        next_phase=Phase.DISCOVER,
                        error=error_msg,
                    )

                # Handle missing placeholders (partial success)
                if replacement_result.missing_placeholders:
                    # Store pending actions for next iteration
                    if not hasattr(state.memory, "pending_actions"):
                        state.memory.pending_actions = []
                    state.memory.pending_actions.extend(replacement_result.pending_actions)

                    # Build error message with specific missing placeholders
                    placeholder_types = {}
                    for ph in replacement_result.missing_placeholders:
                        ph_type = PlaceholderReplacer._detect_placeholder_type(ph)
                        if ph_type not in placeholder_types:
                            placeholder_types[ph_type] = []
                        placeholder_types[ph_type].append(ph)

                    error_parts = [
                        f"Placeholder replacement incomplete: {len(replacement_result.missing_placeholders)} placeholders missing."
                    ]
                    for ph_type, ph_list in placeholder_types.items():
                        error_parts.append(f"  Missing {ph_type}: {', '.join(ph_list)}")
                    error_parts.append(
                        f"Successfully processed {replacement_result.replaced_count}/{replacement_result.total_count} actions. "
                        f"Please provide the missing placeholders in your next response using the format: "
                        f"---(({replacement_result.missing_placeholders[0]}))---\n<content>\n---"
                    )

                    error_msg = "\n".join(error_parts)
                    logger.warning(f"[PlanPhase] {error_msg}")
                    state.last_error.summary = error_msg

                    # Use only successful actions for this iteration
                    actions = successful_actions

                    # If no successful actions, transition back to DISCOVER
                    if not actions:
                        logger.warning(
                            "[PlanPhase] No successful actions after placeholder replacement. "
                            "Transitioning back to DISCOVER to allow LLM to retry."
                        )
                        self.coordinator.state_manager.update(phase="DISCOVER")
                        self._transition(Phase.DISCOVER)
                        return PhaseResult(
                            success=False,
                            data={},
                            next_phase=Phase.DISCOVER,
                            error=error_msg,
                        )
                else:
                    # All placeholders replaced successfully
                    actions = successful_actions

            except PlaceholderReplacementError as e:
                logger.error(
                    f"[PlanPhase] Placeholder replacement failed: {e}. "
                    f"Missing placeholders: {e.missing_placeholders}"
                )
                # Set error state
                state.last_error.summary = str(e)
                # Transition back to DISCOVER for retry
                self.coordinator.state_manager.update(phase="DISCOVER")
                self._transition(Phase.DISCOVER)
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.DISCOVER,
                    error=str(e),
                )

            # Final validation: ensure no unreplaced placeholders remain in successful actions
            is_valid, remaining = PlaceholderReplacer.validate_replacement(actions, file_contents)
            if not is_valid:
                error_msg = (
                    f"CRITICAL: {len(remaining)} actions still have unreplaced placeholders after replacement: {remaining}. "
                    f"This indicates a bug in placeholder replacement logic."
                )
                logger.error(f"[PlanPhase] {error_msg}")
                state.last_error.summary = error_msg
                self.coordinator.state_manager.update(phase="DISCOVER")
                self._transition(Phase.DISCOVER)
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.DISCOVER,
                    error=error_msg,
                )

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
                decision_record["current_step_thoughts"] = action_json.current_step_thoughts
                decision_record["plan"] = action_json.plan
                decision_record["actions"] = [
                    a.to_dict() if hasattr(a, "to_dict") else a for a in actions
                ]

                # CRITICAL: Update state.memory.plan with LLM's plan for Long-term Memory
                # This ensures the plan is visible in formatted memory context
                if action_json.plan:
                    state.memory.plan = action_json.plan
                    logger.info(
                        f"[PlanPhase] Updated long-term memory plan: "
                        f"{len(action_json.plan) if isinstance(action_json.plan, list) else 'string'} items"
                    )

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
                    "current_step_thoughts": action_json.current_step_thoughts,
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

            # Track important decisions for Long-term Memory
            # Important decisions include: task completion, task failure, significant actions
            self._track_important_decision(state, action_json, stop_reason, actions)

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

    def _track_important_decision(
        self, state: Any, action_json: Any, stop_reason: str, actions: list
    ) -> None:
        """
        Track important decisions for Long-term Memory.

        Important decisions are tracked when:
        - Task is marked as done or failed
        - First plan is created (significant step)
        - Multiple file operations are planned (significant action)

        Args:
            state: Agent state
            action_json: Parsed action JSON from LLM
            stop_reason: Current stop reason
            actions: List of actions
        """
        from atloop.memory.memory_manager import MemoryManager

        # Track task completion or failure (always important)
        if stop_reason == "done":
            result_msg = ""
            if action_json and action_json.result_message:
                result_msg = f": {action_json.result_message}"
            MemoryManager.add_important_decision(
                state,
                f"Task completed{result_msg}",
                state.step,
                {"stop_reason": stop_reason, "actions_count": len(actions)},
            )
            logger.info("[PlanPhase] Tracked important decision: task completed")

        elif stop_reason == "fail":
            result_msg = ""
            if action_json and action_json.result_message:
                result_msg = f": {action_json.result_message}"
            MemoryManager.add_important_decision(
                state,
                f"Task failed{result_msg}",
                state.step,
                {"stop_reason": stop_reason, "actions_count": len(actions)},
            )
            logger.info("[PlanPhase] Tracked important decision: task failed")

        # Track first plan creation (if plan has multiple steps)
        elif action_json and action_json.plan and len(state.memory.important_decisions) == 0:
            if isinstance(action_json.plan, list) and len(action_json.plan) >= 3:
                # Create a more readable plan preview with full step text
                plan_steps = action_json.plan[:5]  # Show up to 5 steps
                plan_preview = "; ".join(str(s)[:50] for s in plan_steps)
                if len(plan_preview) > 200:
                    plan_preview = plan_preview[:200] + "..."
                if len(action_json.plan) > 5:
                    plan_preview += f" (+{len(action_json.plan) - 5} more steps)"
                MemoryManager.add_important_decision(
                    state,
                    f"Initial plan ({len(action_json.plan)} steps): {plan_preview}",
                    state.step,
                    {"plan_steps": len(action_json.plan)},
                )
                logger.info("[PlanPhase] Tracked important decision: initial plan created")

        # Track significant file operations (5+ actions)
        elif len(actions) >= 5:
            tools_used = [a.get("tool", "?") for a in actions[:5]]
            tools_str = ", ".join(tools_used)
            MemoryManager.add_important_decision(
                state,
                f"Large batch of actions ({len(actions)} total): {tools_str}...",
                state.step,
                {"actions_count": len(actions)},
            )
            logger.info("[PlanPhase] Tracked important decision: large batch of actions")

    def _save_llm_io(
        self, step: int, input_text: Optional[str], output_text: Optional[str], io_type: str
    ) -> None:
        """
        Save LLM input or output to file for debugging.

        Args:
            step: Step number
            input_text: LLM input text (None if saving output)
            output_text: LLM output text (None if saving input)
            io_type: "input" or "output"
        """
        try:
            # Get run directory from event logger
            log_dir = self.coordinator.event_logger.log_dir

            # Create debug subdirectory
            debug_dir = log_dir / "debug"
            debug_dir.mkdir(exist_ok=True)

            # Save to file
            filename = debug_dir / f"step_{step:03d}_{io_type}.txt"
            content = input_text if input_text else output_text
            if content:
                filename.write_text(content, encoding="utf-8")
                logger.debug(f"[PlanPhase] Saved LLM {io_type} to {filename}")
        except Exception as e:
            logger.warning(f"[PlanPhase] Failed to save LLM {io_type}: {e}")
