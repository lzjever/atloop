"""Budget management for agent execution."""

from datetime import datetime
from typing import Optional

from atloop.config.models import Budget
from atloop.memory.state import BudgetUsed


class BudgetManager:
    """Manage execution budget."""

    def __init__(self, budget: Budget, start_time: Optional[datetime] = None):
        """
        Initialize budget manager.

        Args:
            budget: Budget configuration
            start_time: Start time (default: now)
        """
        self.budget = budget
        self.start_time = start_time or datetime.now()
        self.budget_used = BudgetUsed()

    def check_llm_calls(self) -> tuple[bool, Optional[str]]:
        """
        Check if LLM calls budget is exhausted.

        Returns:
            Tuple of (within_budget, error_message)
        """
        if self.budget_used.llm_calls >= self.budget.max_llm_calls:
            return False, f"达到最大LLM调用次数限制: {self.budget.max_llm_calls}"
        return True, None

    def check_tool_calls(self) -> tuple[bool, Optional[str]]:
        """
        Check if tool calls budget is exhausted.

        Returns:
            Tuple of (within_budget, error_message)
        """
        if self.budget_used.tool_calls >= self.budget.max_tool_calls:
            return False, f"达到最大工具调用次数限制: {self.budget.max_tool_calls}"
        return True, None

    def check_wall_time(self) -> tuple[bool, Optional[str]]:
        """
        Check if wall time budget is exhausted.

        Returns:
            Tuple of (within_budget, error_message)
        """
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if elapsed >= self.budget.max_wall_time_sec:
            return False, f"达到最大执行时间限制: {self.budget.max_wall_time_sec} 秒"
        return True, None

    def check_all(self) -> tuple[bool, Optional[str]]:
        """
        Check all budget constraints.

        Returns:
            Tuple of (within_budget, error_message)
        """
        # Check LLM calls
        ok, msg = self.check_llm_calls()
        if not ok:
            return False, msg

        # Check tool calls
        ok, msg = self.check_tool_calls()
        if not ok:
            return False, msg

        # Check wall time
        ok, msg = self.check_wall_time()
        if not ok:
            return False, msg

        return True, None

    def update_wall_time(self):
        """Update wall time usage."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.budget_used.wall_time_sec = int(elapsed)
