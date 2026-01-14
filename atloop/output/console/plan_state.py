"""Plan state management for efficient plan queries.

This module provides PlanState class that encapsulates plan query logic
with caching to avoid repeated traversals.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class PlanState:
    """Encapsulates plan state query logic with caching.
    
    This class provides efficient queries for plan information,
    with caching to avoid repeated O(n) traversals.
    
    Responsibilities:
    - Parse plan steps (PlanStep, dict, string with emoji)
    - Cache query results (position, entry, status)
    - Track state changes for minimal mode
    - Provide O(1) query interface after caching
    """
    
    plan: Optional[List[Any]] = None
    
    # Cached query results (computed on plan update)
    _current_position: int = 0  # 1-based, 0 means no active task
    _current_entry: Optional[str] = None
    _current_status: Optional[str] = None
    _total: int = 0
    
    # Change tracking for minimal mode
    _last_displayed_position: int = -1
    _last_displayed_status: Optional[str] = None
    
    def update_plan(self, plan: Optional[List[Any]]) -> bool:
        """Update plan and recompute cached state.
        
        Args:
            plan: New plan list (List[PlanStep], List[dict], or List[str])
        
        Returns:
            True if plan changed, False otherwise
        """
        if self.plan == plan:
            return False
        
        self.plan = plan
        self._recompute_state()
        return True
    
    def _recompute_state(self) -> None:
        """Recompute all cached state from plan.
        
        This method is called whenever plan is updated.
        It finds the current active task (in_progress or first pending)
        and caches the results for O(1) queries.
        """
        if not self.plan:
            self._current_position = 0
            self._current_entry = None
            self._current_status = None
            self._total = 0
            return
        
        self._total = len(self.plan)
        
        # Find in_progress task first (highest priority)
        for i, step in enumerate(self.plan):
            status = self._get_step_status(step)
            if status == "in_progress":
                self._current_position = i + 1
                self._current_entry = self._extract_description(step)
                self._current_status = status
                return
        
        # If no in_progress, find first pending
        for i, step in enumerate(self.plan):
            status = self._get_step_status(step)
            if status == "pending":
                self._current_position = i + 1
                self._current_entry = self._extract_description(step)
                self._current_status = status
                return
        
        # No active task found (all completed or all not started)
        self._current_position = 0
        self._current_entry = None
        self._current_status = None
    
    def _get_step_status(self, step: Any) -> Optional[str]:
        """Extract status from a plan step (supports multiple formats).
        
        Args:
            step: Plan step (PlanStep, dict, or string with emoji)
        
        Returns:
            Status string ("in_progress", "completed", "pending", etc.) or None
        """
        # PlanStep object
        if hasattr(step, "status"):
            return step.status
        
        # Dict format
        if isinstance(step, dict):
            return step.get("status")
        
        # String format with emoji markers
        if isinstance(step, str):
            step_str = step.strip()
            if "↻" in step_str or "🔄" in step_str:
                return "in_progress"
            elif "✓" in step_str or "✅" in step_str:
                return "completed"
            elif "≡" in step_str or "⏳" in step_str:
                return "pending"
            elif "❌" in step_str or "✗" in step_str:
                return "failed"
            elif "⏭️" in step_str:
                return "skipped"
            # Default to pending if no marker found
            return "pending"
        
        return None
    
    def _extract_description(self, step: Any) -> str:
        """Extract description from plan step.
        
        Args:
            step: Plan step (PlanStep, dict, or string with emoji)
        
        Returns:
            Description string (with emoji removed if string format)
        """
        # PlanStep object
        if hasattr(step, "description"):
            return step.description
        
        # Dict format
        if isinstance(step, dict):
            return step.get("description", step.get("id", ""))
        
        # String format - remove emoji markers
        step_str = str(step).strip()
        for emoji in ["↻", "🔄", "✓", "✅", "≡", "⏳", "❌", "✗", "⏭️"]:
            step_str = step_str.replace(emoji, "")
        return step_str.strip()
    
    # Public query interface (all O(1) after caching)
    
    def get_position(self) -> tuple[int, int]:
        """Get (current, total) plan position.
        
        Returns:
            Tuple of (current_position, total_count)
            current_position is 1-based, 0 means no active task
        """
        return (self._current_position, self._total)
    
    def get_current_entry(self) -> Optional[str]:
        """Get current plan entry description.
        
        Returns:
            Description of current plan entry, or None if no active task
        """
        return self._current_entry
    
    def get_current_status(self) -> Optional[str]:
        """Get current plan entry status.
        
        Returns:
            Status string ("in_progress", "pending", etc.) or None
        """
        return self._current_status
    
    def has_changed(self) -> bool:
        """Check if plan state has changed since last display.
        
        This method tracks position and status changes for minimal mode.
        It updates the tracking state when a change is detected.
        
        Returns:
            True if plan position or status changed, False otherwise
        """
        if (self._current_position != self._last_displayed_position or
            self._current_status != self._last_displayed_status):
            self._last_displayed_position = self._current_position
            self._last_displayed_status = self._current_status
            return True
        return False
