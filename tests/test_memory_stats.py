"""Tests for memory statistics display formatting."""

from unittest.mock import patch

from atloop.memory.state import AgentState, BudgetUsed, LastError, Memory
from atloop.orchestrator.memory_stats import format_memory_stats


class TestMemoryStatsFormatting:
    """Test memory statistics formatting with PrettyTable."""

    def test_format_memory_stats_basic(self):
        """Test basic memory stats formatting with minimal data."""
        state = AgentState(
            step=1,
            phase="PLAN",
            memory=Memory(),
            budget_used=BudgetUsed(llm_calls=0, tool_calls=0, wall_time_sec=0),
        )

        result = format_memory_stats(state)

        # Check header
        assert "📊 Memory Stats" in result
        assert "Step 1" in result
        assert "Phase: PLAN" in result

        # Check table structure
        assert "📁 Files" in result
        assert "🔧 Execution" in result
        assert "🧠 Memory" in result
        assert "💰 Budget" in result

        # Check values are zero
        assert "Created: 0" in result
        assert "Modified: 0" in result
        assert "Attempts: 0" in result
        assert "LLM: 0" in result
        assert "Tools: 0" in result

    def test_format_memory_stats_with_data(self):
        """Test memory stats formatting with actual data."""
        memory = Memory()
        memory.created_files = ["file1.py", "file2.py", "file3.py"]
        memory.modified_files_content = [
            {"path": "file1.py", "content": "content1"},
            {"path": "file2.py", "content": "content2"},
        ]
        memory.attempts = [{"step": 1}, {"step": 2}, {"step": 3}, {"step": 4}]
        memory.tool_results_history = [{"tool": "read_file"}, {"tool": "write_file"}]
        memory.plan = ["Step 1", "Step 2", "Step 3"]
        memory.important_decisions = [{"decision": "dec1"}, {"decision": "dec2"}]
        memory.milestones = [{"milestone": "mil1"}]

        state = AgentState(
            step=5,
            phase="ACT",
            memory=memory,
            budget_used=BudgetUsed(llm_calls=10, tool_calls=25, wall_time_sec=120),
        )

        result = format_memory_stats(state)

        # Check counts
        assert "Created: 3" in result
        assert "Modified: 2" in result
        assert "Attempts: 4" in result
        assert "Tool Results: 2" in result
        assert "Plan: 3 items" in result
        assert "Decisions: 2" in result
        assert "Milestones: 1" in result
        assert "LLM: 10" in result
        assert "Tools: 25" in result
        assert "Time: 120s" in result

    def test_format_memory_stats_with_string_plan(self):
        """Test memory stats with string plan instead of list."""
        memory = Memory()
        memory.plan = "Step 1\nStep 2\nStep 3\nStep 4"

        state = AgentState(
            step=2,
            phase="PLAN",
            memory=memory,
            budget_used=BudgetUsed(llm_calls=5, tool_calls=10, wall_time_sec=60),
        )

        result = format_memory_stats(state)

        # Check plan size is calculated correctly (4 lines)
        assert "Plan: 4 items" in result

    def test_format_memory_stats_with_empty_plan(self):
        """Test memory stats with empty plan."""
        memory = Memory()
        memory.plan = ""

        state = AgentState(
            step=1,
            phase="PLAN",
            memory=memory,
            budget_used=BudgetUsed(llm_calls=1, tool_calls=2, wall_time_sec=5),
        )

        result = format_memory_stats(state)

        # Check plan shows 0 items
        assert "Plan: 0 items" in result

    def test_format_memory_stats_with_error(self):
        """Test memory stats includes error information when present."""
        state = AgentState(
            step=3,
            phase="ACT",
            memory=Memory(),
            budget_used=BudgetUsed(llm_calls=5, tool_calls=10, wall_time_sec=30),
            last_error=LastError(summary="Test error message here"),
        )

        result = format_memory_stats(state)

        # Check error is displayed
        assert "⚠️  Last Error" in result
        assert "Test error message here" in result

    def test_format_memory_stats_with_long_error(self):
        """Test memory stats truncates long error messages."""
        long_error = "A" * 200  # 200 characters
        state = AgentState(
            step=4,
            phase="VERIFY",
            memory=Memory(),
            budget_used=BudgetUsed(llm_calls=8, tool_calls=15, wall_time_sec=45),
            last_error=LastError(summary=long_error),
        )

        result = format_memory_stats(state)

        # Check error is truncated to 150 chars
        error_line = [line for line in result.split("\n") if "⚠️  Last Error" in line][0]
        # Error preview should be max 150 chars + "⚠️  Last Error: " prefix
        assert len(error_line) < 200

    def test_format_memory_stats_table_structure(self):
        """Test that the output has proper table structure."""
        state = AgentState(
            step=1,
            phase="PLAN",
            memory=Memory(),
            budget_used=BudgetUsed(llm_calls=1, tool_calls=2, wall_time_sec=3),
        )

        result = format_memory_stats(state)
        lines = result.split("\n")

        # Check separator lines
        assert "=" * 70 in result

        # Check table is present (should have multiple rows)
        # The table should have at least 7 data rows + borders
        table_lines = [
            line for line in lines if "│" in line or "─" in line or "┌" in line or "└" in line
        ]
        assert len(table_lines) > 0  # Table borders/separators should be present

    def test_format_memory_stats_compact_height(self):
        """Test that the output is compact (not too many lines)."""
        state = AgentState(
            step=1,
            phase="PLAN",
            memory=Memory(),
            budget_used=BudgetUsed(llm_calls=1, tool_calls=2, wall_time_sec=3),
        )

        result = format_memory_stats(state)
        lines = result.split("\n")

        # Should be compact - total lines should be reasonable (around 15-20)
        # Header (3 lines) + Table (7-10 lines) + Footer (3 lines) = ~13-16 lines
        assert len([l for l in lines if l.strip()]) <= 20

    def test_format_memory_stats_all_categories_present(self):
        """Test that all main categories are present in output."""
        memory = Memory()
        memory.created_files = ["test.py"]
        memory.modified_files_content = [{"path": "test.py"}]
        memory.attempts = [{"step": 1}]
        memory.tool_results_history = [{"tool": "read_file"}]
        memory.plan = ["Step 1"]
        memory.important_decisions = [{"decision": "test"}]
        memory.milestones = [{"milestone": "test"}]

        state = AgentState(
            step=1,
            phase="PLAN",
            memory=memory,
            budget_used=BudgetUsed(llm_calls=1, tool_calls=2, wall_time_sec=3),
        )

        result = format_memory_stats(state)

        # Check all main sections are present
        assert "📁 Files" in result
        assert "🔧 Execution" in result
        assert "🧠 Memory" in result
        assert "💰 Budget" in result


class TestMemoryStatsSimpleFormat:
    """Test fallback simple format when PrettyTable is not available."""

    @patch("atloop.orchestrator.memory_stats.PrettyTable", None)
    def test_format_memory_stats_simple_fallback(self):
        """Test simple format fallback when PrettyTable is not available."""
        memory = Memory()
        memory.created_files = ["file1.py", "file2.py"]
        memory.modified_files_content = [{"path": "file1.py"}]
        memory.attempts = [{"step": 1}, {"step": 2}]
        memory.tool_results_history = [{"tool": "read_file"}]
        memory.plan = ["Step 1", "Step 2"]
        memory.important_decisions = [{"decision": "dec1"}]
        memory.milestones = [{"milestone": "mil1"}]

        state = AgentState(
            step=3,
            phase="ACT",
            memory=memory,
            budget_used=BudgetUsed(llm_calls=5, tool_calls=10, wall_time_sec=60),
        )

        result = format_memory_stats(state)

        # Check header
        assert "📊 Memory Stats" in result
        assert "Step 3" in result
        assert "Phase: ACT" in result

        # Check all data is present in simple format
        assert "Created=2" in result
        assert "Modified=1" in result
        assert "Attempts=2" in result
        assert "Tool Results=1" in result
        assert "Plan=2 items" in result
        assert "Decisions=1" in result
        assert "Milestones=1" in result
        assert "LLM=5" in result
        assert "Tools=10" in result
        assert "Time=60s" in result

    @patch("atloop.orchestrator.memory_stats.PrettyTable", None)
    def test_format_memory_stats_simple_with_error(self):
        """Test simple format includes error when present."""
        state = AgentState(
            step=1,
            phase="PLAN",
            memory=Memory(),
            budget_used=BudgetUsed(llm_calls=1, tool_calls=2, wall_time_sec=3),
            last_error=LastError(summary="Simple error test"),
        )

        result = format_memory_stats(state)

        assert "⚠️  Last Error" in result
        assert "Simple error test" in result

    @patch("atloop.orchestrator.memory_stats.PrettyTable", None)
    def test_format_memory_stats_simple_compact(self):
        """Test simple format is compact."""
        state = AgentState(
            step=1,
            phase="PLAN",
            memory=Memory(),
            budget_used=BudgetUsed(llm_calls=1, tool_calls=2, wall_time_sec=3),
        )

        result = format_memory_stats(state)
        lines = result.split("\n")

        # Simple format should be very compact (around 6-8 lines)
        non_empty_lines = [l for l in lines if l.strip()]
        assert len(non_empty_lines) <= 8


class TestMemoryStatsEdgeCases:
    """Test edge cases for memory stats formatting."""

    def test_format_memory_stats_empty_state(self):
        """Test formatting with completely empty state."""
        state = AgentState(
            step=0,
            phase="DISCOVER",
            memory=Memory(),
            budget_used=BudgetUsed(),
        )

        result = format_memory_stats(state)

        # Should still produce valid output
        assert "📊 Memory Stats" in result
        assert "Step 0" in result
        assert "Created: 0" in result

    def test_format_memory_stats_large_numbers(self):
        """Test formatting with large numbers."""
        memory = Memory()
        memory.created_files = ["file"] * 1000
        memory.attempts = [{"step": i} for i in range(500)]
        memory.plan = [f"Step {i}" for i in range(200)]

        state = AgentState(
            step=100,
            phase="ACT",
            memory=memory,
            budget_used=BudgetUsed(llm_calls=999, tool_calls=5000, wall_time_sec=3600),
        )

        result = format_memory_stats(state)

        # Check large numbers are displayed correctly
        assert "Created: 1000" in result
        assert "Attempts: 500" in result
        assert "Plan: 200 items" in result
        assert "LLM: 999" in result
        assert "Tools: 5000" in result
        assert "Time: 3600s" in result

    def test_format_memory_stats_special_characters_in_error(self):
        """Test formatting handles special characters in error messages."""
        error_with_special = "Error: {variable} $PATH `command` \\backslash"
        state = AgentState(
            step=1,
            phase="ACT",
            memory=Memory(),
            budget_used=BudgetUsed(llm_calls=1, tool_calls=2, wall_time_sec=3),
            last_error=LastError(summary=error_with_special),
        )

        result = format_memory_stats(state)

        # Should handle special characters without crashing
        assert "⚠️  Last Error" in result
        # Error should be truncated but present
        assert len(result) > 0
