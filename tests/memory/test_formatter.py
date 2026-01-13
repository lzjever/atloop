"""Tests for MemoryFormatter and ToolResultFormatter."""

import pytest

from atloop.memory.formatter import ToolResultFormatter
from tests.memory.fixtures.sample_state import create_sample_state


class TestToolResultFormatter:
    """Tests for ToolResultFormatter."""

    def test_format_single_result_success(self):
        """Test formatting a successful tool result."""
        tool_result = {
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
        }

        formatted = ToolResultFormatter.format_single_result(tool_result)
        
        assert "Step 3" in formatted
        assert "✓" in formatted
        assert "[run]" in formatted
        assert "python3 --version" in formatted
        assert "Python 3.10.12" in formatted
        assert "✅ **Status**: Success" in formatted

    def test_format_single_result_failure(self):
        """Test formatting a failed tool result."""
        tool_result = {
            "step": 12,
            "tool": "run",
            "args": {"cmd": "python3 plot_kline.py"},
            "placeholder": None,
            "result": {
                "ok": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": "FileNotFoundError: Data file 'stock_data.csv' not found",
                "error": "FileNotFoundError",
            },
        }

        formatted = ToolResultFormatter.format_single_result(tool_result)
        
        assert "Step 12" in formatted
        assert "✗" in formatted
        assert "[run]" in formatted
        assert "❌ **Status**: Failed" in formatted
        assert "Exit Code: 1" in formatted
        assert "Root Cause" in formatted

    def test_format_single_result_with_placeholder(self):
        """Test formatting a result with placeholder."""
        tool_result = {
            "step": 7,
            "tool": "write_file",
            "args": {"path": "generate_data.py"},
            "placeholder": "WRITE_FILE_CONTENT_file:generate_data.py",
            "result": {
                "ok": True,
                "exit_code": 0,
                "stdout": "File created successfully",
                "stderr": "",
            },
        }

        formatted = ToolResultFormatter.format_single_result(tool_result)
        
        assert "Step 7" in formatted
        assert "[write_file]" in formatted
        assert "WRITE_FILE_CONTENT_file:generate_data.py" in formatted

    def test_format_single_result_long_output(self):
        """Test formatting a result with long output (truncation)."""
        long_output = "A" * 20000  # 20KB output
        tool_result = {
            "step": 3,
            "tool": "run",
            "args": {"cmd": "cat large_file.txt"},
            "placeholder": None,
            "result": {
                "ok": True,
                "exit_code": 0,
                "stdout": long_output,
                "stderr": "",
            },
        }

        formatted = ToolResultFormatter.format_single_result(tool_result)
        
        # Should be truncated
        assert len(formatted) < len(long_output)
        assert "... [Omitted" in formatted or len(formatted) < 15000

    def test_format_results_list(self):
        """Test formatting a list of tool results."""
        tool_results = [
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

        formatted = ToolResultFormatter.format_results_list(tool_results)
        
        assert "Step 3" in formatted
        assert formatted.count("Step 3") == 2  # Both results from step 3

    def test_format_results_list_max_count(self):
        """Test that max_count limit is respected."""
        tool_results = [
            {
                "step": i,
                "tool": "run",
                "args": {"cmd": f"command_{i}"},
                "placeholder": None,
                "result": {
                    "ok": True,
                    "exit_code": 0,
                    "stdout": f"output_{i}",
                    "stderr": "",
                },
            }
            for i in range(10)
        ]

        formatted = ToolResultFormatter.format_results_list(tool_results, max_count=5)
        
        # Should only show last 5 results
        assert "Step 9" in formatted
        assert "Step 8" in formatted
        assert "Step 7" in formatted
        assert "Step 6" in formatted
        assert "Step 5" in formatted
        assert "Step 4" not in formatted

    def test_format_results_empty(self):
        """Test formatting an empty list."""
        formatted = ToolResultFormatter.format_results_list([])
        assert formatted == ""

    def test_format_single_result_file_tool(self):
        """Test formatting a file tool result."""
        tool_result = {
            "step": 7,
            "tool": "write_file",
            "args": {"path": "generate_data.py"},
            "placeholder": None,
            "result": {
                "ok": True,
                "exit_code": 0,
                "stdout": "File created successfully",
                "stderr": "",
            },
        }

        formatted = ToolResultFormatter.format_single_result(tool_result)
        
        assert "[write_file]" in formatted
        assert "path: generate_data.py" in formatted
        assert "File created successfully" in formatted
