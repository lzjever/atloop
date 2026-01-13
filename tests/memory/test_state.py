"""Tests for Memory state module."""

import pytest

from atloop.memory.state import AgentState, Artifacts, BudgetUsed, LastError, Memory
from tests.memory.fixtures.sample_state import create_sample_state
from tests.memory.test_helpers import assert_memory_format_valid


class TestMemoryGetFormattedContext:
    """Tests for Memory.get_formatted_context() method."""

    def test_get_formatted_context(self):
        """Test basic get_formatted_context functionality."""
        state = create_sample_state(step=7, stage="mid", task_goal="Test task")

        context = state.memory.get_formatted_context(
            state=state,
            task_goal="Test task",
        )

        assert isinstance(context, str)
        assert len(context) > 0
        assert "Task Overview" in context
        assert "Execution Plan" in context

    def test_get_formatted_context_with_options(self):
        """Test get_formatted_context with format options."""
        state = create_sample_state(step=7, stage="mid")

        context = state.memory.get_formatted_context(
            state=state,
            format_options={
                "tool_results_count": 3,
                "steps_summary_count": 2,
                "include_file_content": False,
            },
        )

        assert isinstance(context, str)
        assert len(context) > 0

    def test_get_formatted_context_length_limit(self):
        """Test get_formatted_context with length limit."""
        state = create_sample_state(step=7, stage="mid")

        context = state.memory.get_formatted_context(
            state=state,
            max_length=500,
        )

        assert isinstance(context, str)
        assert len(context) <= 550  # Allow some margin

    def test_get_formatted_context_empty(self):
        """Test get_formatted_context with empty memory."""
        state = AgentState(
            step=1,
            phase="PLAN",
            memory=Memory(),
            last_error=LastError(),
            artifacts=Artifacts(),
            budget_used=BudgetUsed(),
        )

        context = state.memory.get_formatted_context(
            state=state,
            task_goal="Test task",
        )

        assert isinstance(context, str)
        assert "Task Overview" in context

    def test_get_formatted_context_format_valid(self):
        """Test that formatted context matches design format."""
        state = create_sample_state(step=7, stage="mid", task_goal="Test task")

        context = state.memory.get_formatted_context(
            state=state,
            task_goal="Test task",
        )

        # Verify format is valid
        assert_memory_format_valid(context)
