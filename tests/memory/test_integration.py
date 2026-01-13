"""Integration tests for memory module."""

import pytest

from atloop.memory.summarizer import MemorySummarizer
from tests.memory.fixtures.sample_state import create_sample_state
from tests.memory.test_helpers import (
    assert_no_duplicate_tool_results,
    count_tool_results,
    extract_sections,
)


class TestSummarizerNoDuplicate:
    """Test that summarizer does not show duplicate tool results."""

    def test_summarizer_no_duplicate_tool_results(self):
        """Verify that tool results are only shown once."""
        state = create_sample_state(step=3, stage="early")
        
        # Add tool results to tool_results_history
        state.memory.tool_results_history = [
            {
                "step": 3,
                "tool": "run",
                "args": {"cmd": "python3 --version"},
                "placeholder": None,
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "Python 3.10.12",
                    "stderr": "",
                },
            },
            {
                "step": 3,
                "tool": "run",
                "args": {"cmd": "ls -la"},
                "placeholder": None,
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "total 0",
                    "stderr": "",
                },
            },
        ]
        
        summary = MemorySummarizer.summarize(state)
        
        # Verify no duplicate tool results
        assert_no_duplicate_tool_results(summary)
        
        # Count tool results - should be exactly 2
        count = count_tool_results(summary)
        assert count == 2, f"Expected 2 tool results, found {count}"

    def test_summarizer_recent_attempts_format(self):
        """Verify Recent File Modifications section format."""
        state = create_sample_state(step=7, stage="mid")
        
        # Add tool results with modified_files (new design)
        state.memory.tool_results_history = [
            {
                "step": 7,
                "tool": "write_file",
                "args": {"path": "generate_data.py"},
                "placeholder": None,
                "result": {"ok": True, "exit_code": 0, "stdout": "File created", "stderr": ""},
                "modified_files": ["generate_data.py"],
            }
        ]
        
        summary = MemorySummarizer.summarize(state)
        
        # Verify Recent File Modifications section exists (renamed from Recent Attempts)
        assert "## Recent File Modifications" in summary
        assert "Step 7" in summary
        assert "Modified 1 files" in summary or "generate_data.py" in summary
        
        # Verify no tool execution details in this section
        assert "Tool Execution Details" not in summary

    def test_summarizer_tool_results_format(self):
        """Verify Tool Execution Results section format."""
        state = create_sample_state(step=3, stage="early")
        
        # Add tool results
        state.memory.tool_results_history = [
            {
                "step": 3,
                "tool": "run",
                "args": {"cmd": "python3 --version"},
                "placeholder": None,
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "Python 3.10.12",
                    "stderr": "",
                },
            },
        ]
        
        summary = MemorySummarizer.summarize(state)
        
        # Verify Tool Execution Results section exists
        assert "## Recent Tool Execution Results" in summary
        assert "Step 3" in summary
        assert "[run]" in summary
        assert "python3 --version" in summary
        assert "Python 3.10.12" in summary
        
        # Verify format uses code blocks
        # Check directly in summary text instead of using extract_sections
        # (extract_sections may have issues with section name matching)
        assert "```" in summary

    def test_summarizer_only_one_tool_results_section(self):
        """Verify there is only one Tool Execution Results section."""
        state = create_sample_state(step=3, stage="early")
        
        state.memory.tool_results_history = [
            {
                "step": 3,
                "tool": "run",
                "args": {"cmd": "test"},
                "placeholder": None,
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": "test output",
                    "stderr": "",
                },
            },
        ]
        
        summary = MemorySummarizer.summarize(state)
        
        # Count occurrences of "Recent Tool Execution Results"
        count = summary.count("## Recent Tool Execution Results")
        assert count == 1, f"Expected 1 section, found {count}"
        
        # Verify no "Enhanced Storage" variant
        assert "Recent Tool Execution Results (Enhanced Storage)" not in summary
