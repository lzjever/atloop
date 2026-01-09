"""DISCOVER phase implementation."""

import logging

from atloop.memory.summarizer import MemorySummarizer
from atloop.orchestrator.phases.base import BasePhase, PhaseContext, PhaseResult
from atloop.orchestrator.state_machine import Phase

logger = logging.getLogger(__name__)


class DiscoverPhase(BasePhase):
    """DISCOVER phase: Build context and prepare for planning."""

    def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute DISCOVER phase.

        Args:
            context: Phase execution context

        Returns:
            Phase execution result
        """
        logger.debug(f"[DiscoverPhase] Executing DISCOVER phase at step {context.step}")
        state = self.coordinator.state_manager.agent_state

        try:
            # Check if context_builder is initialized
            if self.coordinator.context_builder is None:
                logger.error("[DiscoverPhase] ContextBuilder not initialized")
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.FAIL,
                    error="ContextBuilder not initialized",
                )

            # Build memory summary
            logger.debug("[DiscoverPhase] Building memory summary")
            memory_config = getattr(self.coordinator.config, "memory", None)
            if memory_config:
                memory_summary_max_length = memory_config.summary_max_length
                logger.debug(
                    f"[DiscoverPhase] Using memory config: max_length={memory_summary_max_length}"
                )
            else:
                memory_summary_max_length = 64000
                logger.debug(
                    f"[DiscoverPhase] Using default memory summary max length: {memory_summary_max_length}"
                )

            memory_summary = MemorySummarizer.summarize(
                state,
                max_length=memory_summary_max_length,
                task_goal=self.coordinator.task_spec.goal,
            )
            logger.debug(
                f"[DiscoverPhase] Memory summary length: {len(memory_summary)} chars (max: {memory_summary_max_length})"
            )

            # Extract keywords
            logger.debug("[DiscoverPhase] Extracting keywords")
            keywords = self._extract_keywords()
            logger.debug(f"[DiscoverPhase] Extracted {len(keywords)} keywords: {keywords[:5]}")

            # Build context pack
            logger.debug("[DiscoverPhase] Building context pack")
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
                f"[DiscoverPhase] Context pack built: project_profile={context_pack.project_profile}"
            )

            # Store context pack for PLAN phase
            self.coordinator.job_state.shared_data["context_pack"] = context_pack.to_string()
            logger.debug("[DiscoverPhase] Context pack stored in job_state")

            # Transition to PLAN
            logger.debug("[DiscoverPhase] Transitioning to PLAN phase")
            transition_result = self._transition(Phase.PLAN)
            if not transition_result:
                logger.error("[DiscoverPhase] Transition failed: DISCOVER -> PLAN")
                return PhaseResult(
                    success=False,
                    data={},
                    next_phase=Phase.FAIL,
                    error="State transition failed: DISCOVER -> PLAN",
                )

            self.coordinator.state_manager.update(phase="PLAN")
            logger.info("[DiscoverPhase] Successfully transitioned to PLAN phase")

            return PhaseResult(
                success=True,
                data={"context_pack": context_pack.to_string()},
                next_phase=Phase.PLAN,
            )

        except Exception as e:
            logger.error(f"[DiscoverPhase] Error: {e}")
            logger.debug(
                f"[DiscoverPhase] Exception details: {type(e).__name__}: {e}", exc_info=True
            )
            return PhaseResult(
                success=False,
                data={},
                next_phase=Phase.FAIL,
                error=str(e),
            )

    def _extract_keywords(self) -> list[str]:
        """Extract keywords from state."""
        keywords = []
        state = self.coordinator.state_manager.agent_state

        # Extract from goal
        if self.coordinator.task_spec.goal:
            keywords.extend(
                self.coordinator.indexer.extract_keywords(self.coordinator.task_spec.goal)
            )

        # Extract from error
        if state.last_error.summary:
            keywords.extend(self.coordinator.indexer.extract_keywords(state.last_error.summary))

        return keywords[:10]  # Limit to 10 keywords
