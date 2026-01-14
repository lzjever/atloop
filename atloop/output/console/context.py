"""Formatter context for managing state across formatting components.

This module provides a centralized state manager that tracks execution state
and updates from events. It serves as the single source of truth for formatters.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from atloop.output.console.plan_state import PlanState
from atloop.output.events import (
    LLMResultEvent,
    OutputEvent,
    PhaseTransitionEvent,
    TaskCompleteEvent,
    TaskStartEvent,
    ToolResultEvent,
)


@dataclass
class FormatterContext:
    """Centralized state context for formatters.

    This class maintains execution state and updates from events.
    It serves as the single source of truth for all formatting components.
    """

    # Execution state
    phase: Optional[str] = None
    step: int = 0
    task_id: str = ""
    session_id: Optional[str] = None

    # Plan state (delegated to PlanState for efficient queries)
    plan_state: PlanState = field(default_factory=PlanState)

    # Artifacts
    current_diff: Optional[str] = None

    # Session info
    runs_dir: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # LLM response cache (for plan extraction)
    last_llm_response: Optional[Dict[str, Any]] = None

    def update_from_event(self, event: OutputEvent) -> None:
        """Update context from event.

        Args:
            event: Output event to process
        """
        if isinstance(event, PhaseTransitionEvent):
            self.phase = event.phase
            self.step = event.step

            # Update plan if provided in event
            if hasattr(event, "plan_snapshot") and event.plan_snapshot:
                self.plan_state.update_plan(event.plan_snapshot)

        elif isinstance(event, TaskStartEvent):
            self.task_id = event.task_id
            self.session_id = event.session_id
            self.runs_dir = event.runs_dir
            self.start_time = event.start_time
            self.step = event.step

        elif isinstance(event, TaskCompleteEvent):
            self.end_time = event.end_time
            self.step = event.step

        elif isinstance(event, LLMResultEvent):
            self.last_llm_response = {
                "full_response": event.full_response,
                "actions": event.actions,
                "step": event.step,
            }
            # Extract plan if available
            plan = self._extract_plan_from_response(event)
            if plan:
                self.plan_state.update_plan(plan)

        elif isinstance(event, ToolResultEvent):
            if event.tool_name in ["write_file", "edit_file", "append_file"]:
                # Note: current_diff may not be in event, will be updated separately
                # when we have access to state.artifacts.current_diff
                pass

    # Plan query methods (delegate to plan_state for efficiency)

    def get_current_plan_entry(self) -> Optional[str]:
        """Get current plan entry description.

        Delegates to plan_state for efficient O(1) query.

        Returns:
            Description of current plan entry, or None if not available
        """
        return self.plan_state.get_current_entry()

    def get_plan_position(self) -> tuple[int, int]:
        """Get (current, total) plan position.

        Delegates to plan_state for efficient O(1) query.

        Returns:
            Tuple of (current_position, total_count)
            current_position is 1-based, 0 means no active task
        """
        return self.plan_state.get_position()

    def _extract_plan_from_response(self, event: LLMResultEvent) -> Optional[List[Any]]:
        """Extract plan from LLM response.

        This method tries multiple sources to extract plan information:
        1. Parse from full_response JSON
        2. Extract from actions
        3. Use existing plan in context

        Args:
            event: LLM result event

        Returns:
            Extracted plan list, or None if not found
        """
        # Try to parse from full_response JSON
        if event.full_response:
            try:
                import json

                data = json.loads(event.full_response)
                if "plan" in data and data["plan"]:
                    # Convert to list if needed
                    plan_data = data["plan"]
                    if isinstance(plan_data, list):
                        return plan_data
                    elif isinstance(plan_data, str):
                        # Convert string to list
                        return [line.strip() for line in plan_data.split("\n") if line.strip()]
            except (json.JSONDecodeError, KeyError):
                pass

        # Try to extract from actions (if plan is embedded)
        # This is a fallback - plan extraction from actions is complex
        # For now, we'll rely on state.memory.plan being updated separately
        return None

    def update_plan(self, plan: Optional[List[Any]]) -> None:
        """Update plan from external source (e.g., state.memory.plan).

        Args:
            plan: Plan list (List[PlanStep] or List[str])
        """
        self.plan_state.update_plan(plan)

    def update_diff(self, diff: Optional[str]) -> None:
        """Update current diff.

        Args:
            diff: Diff string or None
        """
        self.current_diff = diff

    def has_plan_state_changed(self) -> bool:
        """Check if plan state has changed since last display.

        Delegates to plan_state for efficient O(1) check.

        Returns:
            True if plan position or status changed, False otherwise
        """
        return self.plan_state.has_changed()

    def _get_current_plan_status(self) -> Optional[str]:
        """Get status of current plan entry.

        Delegates to plan_state for efficient O(1) query.

        Returns:
            Status string ("completed", "in_progress", "pending", etc.) or None
        """
        return self.plan_state.get_current_status()

    # Backward compatibility: expose plan for components that need direct access
    @property
    def plan(self) -> Optional[List[Any]]:
        """Get plan list (for backward compatibility).

        Returns:
            Plan list from plan_state
        """
        return self.plan_state.plan

    @plan.setter
    def plan(self, value: Optional[List[Any]]) -> None:
        """Set plan list (for backward compatibility).

        Args:
            value: Plan list to set
        """
        self.plan_state.update_plan(value)
