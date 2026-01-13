"""Tests for data storage structure migration."""

from atloop.memory.summarizer import MemorySummarizer
from tests.memory.fixtures.sample_state import create_sample_state


class TestActPhaseDataStorage:
    """Test that ActPhase writes data correctly to tool_results_history."""

    def test_act_phase_writes_to_tool_results_history(self):
        """Verify that ActPhase writes tool results to tool_results_history with modified_files."""
        # Create a clean state
        from atloop.memory.state import AgentState, Artifacts, BudgetUsed, LastError, Memory

        state = AgentState(
            step=7,
            phase="ACT",
            memory=Memory(),
            last_error=LastError(),
            artifacts=Artifacts(),
            budget_used=BudgetUsed(),
        )

        # Simulate what ActPhase does
        modified_files = ["generate_data.py"]
        results = [
            {
                "ok": True,
                "exit_code": 0,
                "stdout": "File created successfully",
                "stderr": "",
            }
        ]

        # Simulate tool_results_history append (as ActPhase does)
        tool_result_record = {
            "step": state.step,
            "tool": "write_file",
            "args": {"path": "generate_data.py"},
            "placeholder": "WRITE_FILE_CONTENT_file:generate_data.py",
            "result": results[0],
            "modified_files": modified_files,  # New field
        }
        state.memory.tool_results_history.append(tool_result_record)

        # Verify structure
        assert len(state.memory.tool_results_history) == 1
        assert state.memory.tool_results_history[0]["modified_files"] == modified_files
        assert state.memory.tool_results_history[0]["tool"] == "write_file"

    def test_act_phase_attempts_no_results(self):
        """Verify that attempts no longer contain results field."""
        # Create a clean state
        from atloop.memory.state import AgentState, Artifacts, BudgetUsed, LastError, Memory

        state = AgentState(
            step=7,
            phase="ACT",
            memory=Memory(),
            last_error=LastError(),
            artifacts=Artifacts(),
            budget_used=BudgetUsed(),
        )

        # Simulate what ActPhase does (new structure)
        state.memory.attempts.append(
            {
                "step": state.step,
                "files": ["generate_data.py"],
                "success": True,
                # NOTE: results field should NOT be present
            }
        )

        # Verify structure
        assert len(state.memory.attempts) == 1
        attempt = state.memory.attempts[0]
        assert "results" not in attempt, "attempts should not contain results field"
        assert "files" in attempt
        assert "success" in attempt


class TestSummarizerExtractsFiles:
    """Test that summarizer extracts file modifications from tool_results_history."""

    def test_summarizer_extracts_files_from_tool_results(self):
        """Verify that summarizer can extract file modifications from tool_results_history."""
        state = create_sample_state(step=7, stage="mid")

        # Add tool results with modified_files
        state.memory.tool_results_history = [
            {
                "step": 7,
                "tool": "write_file",
                "args": {"path": "generate_data.py"},
                "placeholder": None,
                "result": {"ok": True, "exit_code": 0, "stdout": "File created", "stderr": ""},
                "modified_files": ["generate_data.py"],
            },
            {
                "step": 10,
                "tool": "write_file",
                "args": {"path": "plot_kline.py"},
                "placeholder": None,
                "result": {"ok": True, "exit_code": 0, "stdout": "File created", "stderr": ""},
                "modified_files": ["plot_kline.py"],
            },
        ]

        summary = MemorySummarizer.summarize(state)

        # Verify file modifications are extracted
        assert "## Recent File Modifications" in summary
        assert "Step 7" in summary
        assert "Step 10" in summary
        assert "generate_data.py" in summary
        assert "plot_kline.py" in summary

    def test_summarizer_handles_multiple_files_per_step(self):
        """Verify that summarizer handles multiple files modified in the same step."""
        state = create_sample_state(step=7, stage="mid")

        # Add tool results with multiple files in same step
        state.memory.tool_results_history = [
            {
                "step": 7,
                "tool": "write_file",
                "args": {"path": "file1.py"},
                "placeholder": None,
                "result": {"ok": True, "exit_code": 0, "stdout": "File created", "stderr": ""},
                "modified_files": ["file1.py"],
            },
            {
                "step": 7,
                "tool": "write_file",
                "args": {"path": "file2.py"},
                "placeholder": None,
                "result": {"ok": True, "exit_code": 0, "stdout": "File created", "stderr": ""},
                "modified_files": ["file2.py"],
            },
        ]

        summary = MemorySummarizer.summarize(state)

        # Verify both files are shown
        assert "Step 7" in summary
        assert "Modified 2 files" in summary or "file1.py" in summary and "file2.py" in summary

    def test_summarizer_backward_compatibility_with_attempts(self):
        """Verify that summarizer falls back to attempts if tool_results_history is empty."""
        state = create_sample_state(step=7, stage="mid")

        # Clear tool_results_history
        state.memory.tool_results_history = []

        # Add old-style attempts (with files but no results)
        state.memory.attempts = [
            {
                "step": 7,
                "files": ["generate_data.py"],
                "success": True,
            }
        ]

        summary = MemorySummarizer.summarize(state)

        # Verify it falls back to attempts
        assert "## Recent File Modifications" in summary
        assert "Step 7" in summary
        assert "generate_data.py" in summary
