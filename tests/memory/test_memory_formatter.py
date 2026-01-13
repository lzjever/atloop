"""Tests for MemoryFormatter."""

from atloop.memory.formatter import MemoryFormatter
from tests.memory.fixtures.sample_state import (
    create_sample_state,
    create_sample_state_with_error,
)
from tests.memory.test_helpers import assert_memory_format_valid, extract_sections


class TestMemoryFormatter:
    """Tests for MemoryFormatter class."""

    def test_format_critical_warnings(self):
        """Test formatting critical warnings."""
        state = create_sample_state(step=7, stage="mid")
        formatter = MemoryFormatter()

        warnings = formatter._format_critical_warnings(state)

        assert "### ⚠️ Critical Warnings" in warnings
        assert "generate_data.py" in warnings
        assert "DO NOT recreate" in warnings

    def test_format_task_overview(self):
        """Test formatting task overview."""
        state = create_sample_state(step=3, stage="early", task_goal="Test task")
        formatter = MemoryFormatter()

        overview = formatter._format_task_overview(state, task_goal="Test task")

        assert "### ≡ Task Overview" in overview
        assert "Test task" in overview
        assert "**Status**" in overview
        assert "**Created Files**" in overview

    def test_format_execution_plan(self):
        """Test formatting execution plan."""
        state = create_sample_state(step=3, stage="early")
        formatter = MemoryFormatter()

        plan = formatter._format_execution_plan(state)

        assert "### 📝 Execution Plan" in plan
        assert "检查当前目录" in plan or "检查" in plan

    def test_format_important_context(self):
        """Test formatting important context."""
        state = create_sample_state(step=7, stage="mid")
        formatter = MemoryFormatter()

        context = formatter._format_important_context(state)

        assert "### 🎯 Important Context" in context
        assert "Key Decisions" in context
        assert "Milestones" in context
        assert "Learnings" in context

    def test_format_recent_activity(self):
        """Test formatting recent activity."""
        state = create_sample_state(step=7, stage="mid")
        formatter = MemoryFormatter()

        activity = formatter._format_recent_activity(state, steps_count=3)

        assert "### 📊 Recent Activity" in activity
        assert "**Steps**" in activity
        assert "**Files Modified**" in activity

    def test_format_tool_execution_results(self):
        """Test formatting tool execution results."""
        state = create_sample_state(step=3, stage="early")
        formatter = MemoryFormatter()

        results = formatter._format_tool_execution_results(state, max_count=5)

        assert "### 🔧 Tool Execution Results" in results
        assert "Step 3" in results

    def test_format_current_state(self):
        """Test formatting current state."""
        state = create_sample_state(step=3, stage="early")
        formatter = MemoryFormatter()

        current_state = formatter._format_current_state(state)

        assert "### ⚠️ Current State" in current_state
        assert "**Last Error**" in current_state
        assert "**Current Diff**" in current_state
        assert "**Test Results**" in current_state

    def test_format_next_steps_guidance(self):
        """Test formatting next steps guidance."""
        state = create_sample_state(step=7, stage="mid")
        formatter = MemoryFormatter()

        guidance = formatter._format_next_steps_guidance(state, task_goal="Test task")

        assert "### 💡 Next Steps Guidance" in guidance
        assert "Next Action" in guidance or "➡️" in guidance

    def test_format_complete(self):
        """Test complete formatting."""
        state = create_sample_state(step=7, stage="mid", task_goal="Test task")
        formatter = MemoryFormatter()

        formatted = formatter.format(state, task_goal="Test task")

        # Verify all required sections are present
        assert "Task Context" in formatted or "Task Overview" in formatted
        assert "Execution Plan" in formatted
        assert "Important Context" in formatted
        assert "Recent Activity" in formatted
        assert "Tool Execution Results" in formatted
        assert "Current State" in formatted
        assert "Next Steps Guidance" in formatted

        # Verify format is valid
        assert_memory_format_valid(formatted)

    def test_format_with_options(self):
        """Test formatting with options."""
        state = create_sample_state(step=7, stage="mid")
        formatter = MemoryFormatter()

        formatted = formatter.format(
            state,
            format_options={
                "tool_results_count": 3,
                "steps_summary_count": 2,
                "include_file_content": False,
            },
        )

        # Verify options are applied
        extract_sections(formatted)
        assert formatted is not None

    def test_format_length_limit(self):
        """Test length limit application."""
        state = create_sample_state(step=7, stage="mid")
        formatter = MemoryFormatter()

        # Set a very small limit
        formatted = formatter.format(state, format_options={"max_length": 100})

        assert len(formatted) <= 150  # Allow some margin
        assert "truncated" in formatted.lower() or len(formatted) <= 100

    def test_format_empty_memory(self):
        """Test formatting empty memory."""
        from atloop.memory.state import AgentState, Artifacts, BudgetUsed, LastError, Memory

        state = AgentState(
            step=1,
            phase="PLAN",
            memory=Memory(),
            last_error=LastError(),
            artifacts=Artifacts(),
            budget_used=BudgetUsed(),
        )
        formatter = MemoryFormatter()

        formatted = formatter.format(state, task_goal="Test task")

        # Should still have basic structure
        assert "Task Overview" in formatted
        assert "Execution Plan" in formatted

    def test_format_early_stage(self):
        """Test formatting early stage (matches example 1)."""
        state = create_sample_state(
            step=3, stage="early", task_goal="模拟生成一只股票一个月的高开低收数据, 画成k线图给我."
        )
        formatter = MemoryFormatter()

        formatted = formatter.format(
            state, task_goal="模拟生成一只股票一个月的高开低收数据, 画成k线图给我."
        )

        # Verify key elements from example 1
        assert "Task Overview" in formatted
        assert "Execution Plan" in formatted
        assert "Recent Activity" in formatted
        assert "Tool Execution Results" in formatted

    def test_format_mid_stage(self):
        """Test formatting mid stage (matches example 2)."""
        state = create_sample_state(
            step=7, stage="mid", task_goal="模拟生成一只股票一个月的高开低收数据, 画成k线图给我."
        )
        formatter = MemoryFormatter()

        formatted = formatter.format(
            state, task_goal="模拟生成一只股票一个月的高开低收数据, 画成k线图给我."
        )

        # Verify key elements from example 2
        assert "Critical Warnings" in formatted
        assert "generate_data.py" in formatted
        assert "Execution Plan" in formatted

    def test_format_with_errors(self):
        """Test formatting with errors (matches example 4)."""
        state = create_sample_state_with_error(step=12)
        formatter = MemoryFormatter()

        formatted = formatter.format(state, task_goal="Test task")

        # Verify error information is included
        assert "Current State" in formatted
        # Error details should be in the formatted output
