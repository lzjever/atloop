"""Tests for ActPhase result processing utilities."""

import logging
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from atloop.config.limits import (
    ERROR_SUMMARY_LIMIT_FILE_VIEW,
    ERROR_SUMMARY_LIMIT_NORMAL,
    STDERR_TAIL_LIMIT,
    STDOUT_STDERR_LIMIT_FILE_VIEW,
    STDOUT_STDERR_LIMIT_NORMAL,
    STDOUT_STDERR_LIMIT_OTHER,
)
from atloop.memory.state import AgentState, Artifacts, LastError, Memory
from atloop.orchestrator.phases.act_result_processor import (
    ErrorStateManager,
    FileChangeTracker,
    ToolResultFormatter,
)

logger = logging.getLogger(__name__)


class TestToolResultFormatter:
    """Tests for ToolResultFormatter."""

    def test_format_result_summary_basic(self):
        """Test basic result summary formatting."""
        tool = "run"
        args = {"cmd": "echo hello"}
        result = {
            "stdout": "hello\n",
            "stderr": "",
            "error": "",
        }

        summary = ToolResultFormatter.format_result_summary(tool, args, result)

        assert "Tool: run" in summary
        assert "Command: echo hello" in summary
        assert "Stdout" in summary
        assert "hello" in summary
        assert "⚠️ Important" in summary

    def test_format_result_summary_with_error(self):
        """Test formatting result with error message."""
        tool = "run"
        args = {"cmd": "invalid_command"}
        result = {
            "stdout": "",
            "stderr": "command not found",
            "error": "Command failed",
        }

        summary = ToolResultFormatter.format_result_summary(tool, args, result)

        assert "Tool: run" in summary
        assert "Command: invalid_command" in summary
        assert "Error: Command failed" in summary
        assert "Stderr" in summary
        assert "command not found" in summary

    def test_format_result_summary_non_run_tool(self):
        """Test formatting result for non-run tool."""
        tool = "write_file"
        args = {"path": "test.py", "content": "print('hello')"}
        result = {
            "stdout": "",
            "stderr": "",
            "error": "",
        }

        summary = ToolResultFormatter.format_result_summary(tool, args, result)

        assert "Tool: write_file" in summary
        assert "Command:" not in summary  # Non-run tools don't have commands

    def test_format_result_summary_empty_outputs(self):
        """Test formatting result with empty stdout and stderr."""
        tool = "run"
        args = {"cmd": "true"}
        result = {
            "stdout": "",
            "stderr": "",
            "error": "",
        }

        summary = ToolResultFormatter.format_result_summary(tool, args, result)

        assert "Tool: run" in summary
        assert "Command: true" in summary
        # Should not contain Stderr or Stdout sections if empty
        assert "Stderr (" not in summary
        assert "Stdout (" not in summary

    def test_format_result_summary_large_output_truncation(self):
        """Test that large outputs are properly truncated."""
        tool = "run"
        # Use a command that is NOT a file view command to test normal limit
        args = {"cmd": "python script.py"}
        # Create output larger than normal limit (but smaller than file view limit)
        large_output = "x" * (STDOUT_STDERR_LIMIT_NORMAL + 1000)
        result = {
            "stdout": large_output,
            "stderr": "",
            "error": "",
        }

        summary = ToolResultFormatter.format_result_summary(tool, args, result)

        assert "Tool: run" in summary
        assert "omitted" in summary.lower() or "..." in summary
        # Summary should be truncated - check that the formatted output is shorter
        # The summary includes headers, so it will be longer than just the output
        # But the output portion should be truncated
        stdout_section = summary.split("Stdout")[1] if "Stdout" in summary else ""
        # The stdout section should contain truncated content
        assert len(stdout_section) < len(large_output)

    def test_format_result_summary_file_view_command(self):
        """Test formatting result for file view command (different limits)."""
        tool = "run"
        args = {"cmd": "cat file.txt"}
        large_output = "x" * (STDOUT_STDERR_LIMIT_FILE_VIEW + 1000)
        result = {
            "stdout": large_output,
            "stderr": "",
            "error": "",
        }

        summary = ToolResultFormatter.format_result_summary(tool, args, result)

        assert "Tool: run" in summary
        # Should use file view limit (larger)
        assert "omitted" in summary.lower() or "..." in summary

    def test_format_result_summary_both_stdout_stderr(self):
        """Test formatting result with both stdout and stderr."""
        tool = "run"
        args = {"cmd": "python script.py"}
        result = {
            "stdout": "Output line 1\nOutput line 2",
            "stderr": "Warning: something",
            "error": "",
        }

        summary = ToolResultFormatter.format_result_summary(tool, args, result)

        assert "Stdout" in summary
        assert "Stderr" in summary
        assert "Output line 1" in summary
        assert "Warning: something" in summary

    def test_format_result_summary_missing_cmd_in_args(self):
        """Test formatting when cmd is missing in args."""
        tool = "run"
        args = {}  # Missing cmd
        result = {
            "stdout": "output",
            "stderr": "",
            "error": "",
        }

        summary = ToolResultFormatter.format_result_summary(tool, args, result)

        assert "Tool: run" in summary
        assert "Command:" not in summary  # Should not include command if missing


class TestErrorStateManager:
    """Tests for ErrorStateManager."""

    @pytest.fixture
    def mock_state(self):
        """Create a mock AgentState."""
        state = MagicMock(spec=AgentState)
        state.last_error = MagicMock(spec=LastError)
        state.last_error.summary = ""
        state.last_error.repro_cmd = ""
        state.last_error.raw_stderr_tail = ""
        return state

    def test_update_error_state_no_error(self, mock_state):
        """Test that error state is not updated when there's no error."""
        tool = "run"
        args = {"cmd": "echo hello"}
        result = {
            "stdout": "hello",
            "stderr": "",
            "error": "",
        }
        result_summary = "Tool: run\nCommand: echo hello\nStdout: hello"

        updated = ErrorStateManager.update_error_state(
            mock_state, tool, args, result, result_summary
        )

        assert updated is False
        assert mock_state.last_error.summary == ""
        assert mock_state.last_error.repro_cmd == ""

    def test_update_error_state_with_stderr(self, mock_state):
        """Test error state update when stderr is present."""
        tool = "run"
        args = {"cmd": "invalid_command"}
        result = {
            "stdout": "",
            "stderr": "command not found",
            "error": "",
        }
        result_summary = "Tool: run\nCommand: invalid_command\nStderr: command not found"

        updated = ErrorStateManager.update_error_state(
            mock_state, tool, args, result, result_summary
        )

        assert updated is True
        assert mock_state.last_error.summary != ""
        assert "command not found" in mock_state.last_error.summary
        assert mock_state.last_error.repro_cmd == "invalid_command"
        assert mock_state.last_error.raw_stderr_tail == "command not found"

    def test_update_error_state_with_error_field(self, mock_state):
        """Test error state update when error field is present."""
        tool = "write_file"
        args = {"path": "test.py"}
        result = {
            "stdout": "",
            "stderr": "",
            "error": "Permission denied",
        }
        result_summary = "Tool: write_file\nError: Permission denied"

        updated = ErrorStateManager.update_error_state(
            mock_state, tool, args, result, result_summary
        )

        assert updated is True
        assert "Permission denied" in mock_state.last_error.summary

    def test_update_error_state_append_to_existing(self, mock_state):
        """Test that new errors are appended to existing error state."""
        tool = "run"
        args = {"cmd": "command1"}
        result = {
            "stdout": "",
            "stderr": "Error 1",
            "error": "",
        }
        result_summary = "Tool: run\nCommand: command1\nStderr: Error 1"

        # First error
        mock_state.last_error.summary = "Previous error"
        updated = ErrorStateManager.update_error_state(
            mock_state, tool, args, result, result_summary
        )

        assert updated is True
        assert "Previous error" in mock_state.last_error.summary
        assert "Error 1" in mock_state.last_error.summary
        assert "=" * 80 in mock_state.last_error.summary  # Separator

    def test_update_error_state_whitespace_only_stderr(self, mock_state):
        """Test that whitespace-only stderr is not considered an error."""
        tool = "run"
        args = {"cmd": "echo hello"}
        result = {
            "stdout": "hello",
            "stderr": "   \n\t  ",  # Only whitespace
            "error": "",
        }
        result_summary = "Tool: run\nCommand: echo hello"

        updated = ErrorStateManager.update_error_state(
            mock_state, tool, args, result, result_summary
        )

        assert updated is False
        assert mock_state.last_error.summary == ""

    def test_update_error_state_repro_cmd_only_for_run_tool(self, mock_state):
        """Test that repro_cmd is only set for run tool."""
        tool = "write_file"
        args = {"path": "test.py"}
        result = {
            "stdout": "",
            "stderr": "Error",
            "error": "",
        }
        result_summary = "Tool: write_file\nStderr: Error"

        ErrorStateManager.update_error_state(mock_state, tool, args, result, result_summary)

        # repro_cmd should not be set for non-run tools
        assert mock_state.last_error.repro_cmd == ""

    def test_update_error_state_stderr_tail_extraction(self, mock_state):
        """Test that stderr tail is properly extracted."""
        tool = "run"
        args = {"cmd": "test"}
        # Create stderr longer than tail limit
        long_stderr = "x" * (STDERR_TAIL_LIMIT + 100) + "END"
        result = {
            "stdout": "",
            "stderr": long_stderr,
            "error": "",
        }
        result_summary = "Tool: run\nStderr: ..."

        ErrorStateManager.update_error_state(mock_state, tool, args, result, result_summary)

        # Should only keep tail
        assert len(mock_state.last_error.raw_stderr_tail) <= STDERR_TAIL_LIMIT
        assert mock_state.last_error.raw_stderr_tail.endswith("END")

    def test_update_error_state_summary_size_limit(self, mock_state):
        """Test that error summary respects size limits."""
        tool = "run"
        args = {"cmd": "test"}
        # Create very long error
        long_error = "x" * (ERROR_SUMMARY_LIMIT_NORMAL + 1000)
        result = {
            "stdout": "",
            "stderr": long_error,
            "error": "",
        }
        result_summary = f"Tool: run\nStderr: {long_error}"

        ErrorStateManager.update_error_state(mock_state, tool, args, result, result_summary)

        # Summary should be truncated
        assert len(mock_state.last_error.summary) <= ERROR_SUMMARY_LIMIT_NORMAL

    def test_update_error_state_file_view_command_limit(self, mock_state):
        """Test that file view commands use different limit."""
        tool = "run"
        args = {"cmd": "cat file.txt"}  # File view command
        long_error = "x" * (ERROR_SUMMARY_LIMIT_FILE_VIEW + 1000)
        result = {
            "stdout": "",
            "stderr": long_error,
            "error": "",
        }
        result_summary = f"Tool: run\nStderr: {long_error}"

        ErrorStateManager.update_error_state(mock_state, tool, args, result, result_summary)

        # Should use file view limit (larger)
        assert len(mock_state.last_error.summary) <= ERROR_SUMMARY_LIMIT_FILE_VIEW
        assert len(mock_state.last_error.summary) > ERROR_SUMMARY_LIMIT_NORMAL


class TestFileChangeTracker:
    """Tests for FileChangeTracker."""

    @pytest.fixture
    def mock_state(self):
        """Create a mock AgentState."""
        state = MagicMock(spec=AgentState)
        state.memory = MagicMock(spec=Memory)
        state.memory.created_files = []
        state.artifacts = MagicMock(spec=Artifacts)
        state.artifacts.current_diff = ""
        return state

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock coordinator."""
        coordinator = MagicMock()
        coordinator.state_manager = MagicMock()
        coordinator.state_manager.save = MagicMock()
        return coordinator

    def test_track_file_creation_basic(self, mock_state, mock_coordinator):
        """Test basic file creation tracking."""
        file_path = "test.py"
        file_content = "print('hello')"
        modified_files = []

        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, file_path, file_content, modified_files
        )

        assert file_path in modified_files
        assert file_path in mock_state.memory.created_files
        assert mock_coordinator.state_manager.save.called

    def test_track_file_creation_empty_path(self, mock_state, mock_coordinator):
        """Test that empty file path is handled gracefully."""
        file_path = ""
        file_content = "content"
        modified_files = []

        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, file_path, file_content, modified_files
        )

        # Should not add empty path
        assert "" not in modified_files
        assert len(mock_state.memory.created_files) == 0
        assert not mock_coordinator.state_manager.save.called

    def test_track_file_creation_duplicate_file(self, mock_state, mock_coordinator):
        """Test that duplicate files are not added twice."""
        file_path = "test.py"
        file_content = "content"
        modified_files = []

        # First call
        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, file_path, file_content, modified_files
        )

        # Second call with same file
        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, file_path, file_content, modified_files
        )

        # Should only appear once in created_files
        assert mock_state.memory.created_files.count(file_path) == 1
        # But should appear twice in modified_files (tracked per execution)
        assert modified_files.count(file_path) == 2

    def test_track_file_creation_diff_generation(self, mock_state, mock_coordinator):
        """Test that diff is generated for file creation."""
        file_path = "test.py"
        file_content = "line1\nline2\nline3"
        modified_files = []

        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, file_path, file_content, modified_files
        )

        assert mock_state.artifacts.current_diff != ""
        assert file_path in mock_state.artifacts.current_diff
        assert "+++" in mock_state.artifacts.current_diff
        assert "line1" in mock_state.artifacts.current_diff

    def test_track_file_creation_empty_content(self, mock_state, mock_coordinator):
        """Test tracking file with empty content."""
        file_path = "empty.py"
        file_content = ""
        modified_files = []

        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, file_path, file_content, modified_files
        )

        assert file_path in modified_files
        assert file_path in mock_state.memory.created_files
        # Diff should be generated even for empty file (contains header)
        # Empty file has 0 lines, so diff will have header but no content lines
        assert mock_state.artifacts.current_diff != ""
        assert file_path in mock_state.artifacts.current_diff

    def test_track_file_creation_large_file_truncation(self, mock_state, mock_coordinator):
        """Test that large files are truncated in diff."""
        file_path = "large.py"
        # Create file with more than 50 lines
        file_content = "\n".join(f"line{i}" for i in range(100))
        modified_files = []

        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, file_path, file_content, modified_files
        )

        diff = mock_state.artifacts.current_diff
        assert "line0" in diff  # First lines should be present
        assert "line99" not in diff  # Later lines should be truncated
        assert "more lines" in diff.lower()  # Should indicate truncation

    def test_track_file_creation_diff_size_limit(self, mock_state, mock_coordinator):
        """Test that diff respects size limit."""
        file_path = "huge.py"
        # Create very large content
        file_content = "x" * 10000
        modified_files = []

        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, file_path, file_content, modified_files
        )

        # Diff should be limited to 5000 chars
        assert len(mock_state.artifacts.current_diff) <= 5000

    def test_track_file_creation_multiple_files(self, mock_state, mock_coordinator):
        """Test tracking multiple different files."""
        modified_files = []

        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, "file1.py", "content1", modified_files
        )
        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, "file2.py", "content2", modified_files
        )
        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, "file3.py", "content3", modified_files
        )

        assert len(modified_files) == 3
        assert len(mock_state.memory.created_files) == 3
        assert "file1.py" in mock_state.memory.created_files
        assert "file2.py" in mock_state.memory.created_files
        assert "file3.py" in mock_state.memory.created_files

    def test_track_file_creation_no_content(self, mock_state, mock_coordinator):
        """Test tracking file when content is None or missing."""
        file_path = "test.py"
        file_content = None
        modified_files = []

        FileChangeTracker.track_file_creation(
            mock_state, mock_coordinator, file_path, file_content, modified_files
        )

        assert file_path in modified_files
        assert file_path in mock_state.memory.created_files
        # Diff should not be updated if no content
        # (implementation may vary, but should not crash)
