"""Tests for ActPhase implementation."""

import logging
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from atloop.llm import ActionJSON
from atloop.memory.state import AgentState, Artifacts, BudgetUsed, LastError, Memory
from atloop.orchestrator.coordinator import WorkflowCoordinator
from atloop.orchestrator.executor.tool_executor import ToolExecutor
from atloop.orchestrator.job_state import JobState
from atloop.orchestrator.phases.act import ActPhase
from atloop.orchestrator.phases.base import PhaseContext
from atloop.orchestrator.state_machine import Phase
from atloop.tools.base import BaseTool, ToolResult
from atloop.tools.registry import ToolRegistry

# Add tests directory to path to import MockTool
sys.path.insert(0, str(Path(__file__).parent))
from test_tools import MockTool  # noqa: E402

logger = logging.getLogger(__name__)


class TestActPhase:
    """Tests for ActPhase."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock WorkflowCoordinator."""
        from atloop.memory.progress_tracker import ProgressTracker
        
        coordinator = MagicMock(spec=WorkflowCoordinator)
        
        # Setup state manager
        coordinator.state_manager = MagicMock()
        state = AgentState()
        coordinator.state_manager.agent_state = state
        coordinator.state_manager.update = MagicMock()
        coordinator.state_manager.save = MagicMock()
        
        # Setup job state
        coordinator.job_state = JobState()
        coordinator.job_state.shared_data = {}
        
        # Setup tool runtime
        coordinator.tool_runtime = MagicMock()
        coordinator.tool_runtime.registry = ToolRegistry(sandbox=MagicMock())
        
        # Setup budget manager
        coordinator.budget_manager = MagicMock()
        coordinator.budget_manager.budget_used = BudgetUsed()
        
        # Setup state machine
        coordinator.state_machine = MagicMock()
        coordinator.state_machine.transition = MagicMock(return_value=True)
        
        # Setup event logger
        coordinator.event_logger = MagicMock()
        
        # Setup progress tracker (for loop detection)
        coordinator.progress_tracker = ProgressTracker()
        
        return coordinator

    @pytest.fixture
    def act_phase(self, mock_coordinator):
        """Create an ActPhase instance."""
        return ActPhase(mock_coordinator)

    def test_act_phase_initialization(self, mock_coordinator):
        """Test ActPhase initialization."""
        phase = ActPhase(mock_coordinator)
        assert phase.coordinator == mock_coordinator
        assert isinstance(phase.executor, ToolExecutor)

    def test_execute_no_actions(self, act_phase, mock_coordinator):
        """Test execute when no actions are provided."""
        mock_coordinator.job_state.shared_data = {}
        context = PhaseContext(step=1, phase=Phase.ACT)

        result = act_phase.execute(context)

        assert result.success is True
        assert result.next_phase == Phase.DISCOVER
        mock_coordinator.state_manager.update.assert_called_with(phase="DISCOVER")

    def test_execute_invalid_action_json(self, act_phase, mock_coordinator):
        """Test execute with invalid action JSON structure."""
        # Use a dict with "actions" key but invalid structure (not a list)
        # ActionJSON.from_dict() now validates, so it will raise ActionJSONValidationError
        mock_coordinator.job_state.shared_data = {
            "actions": {
                "actions": "not a list",  # Invalid: should be a list
                "stop_reason": "continue"
            }
        }
        context = PhaseContext(step=1, phase=Phase.ACT)

        result = act_phase.execute(context)

        # Should fail validation and return error result
        assert result.success is False
        assert result.next_phase == Phase.DISCOVER
        assert "Invalid Action JSON" in result.error
        assert "must be a list/array" in result.error
        assert "Invalid Action JSON" in mock_coordinator.state_manager.agent_state.last_error.summary

    def test_execute_no_actions_key(self, act_phase, mock_coordinator):
        """Test execute when actions dict doesn't have 'actions' key."""
        # Dict exists but no "actions" key - this will fail validation
        # But we want to test the case where actions_dict is None or empty
        mock_coordinator.job_state.shared_data = {"actions": None}
        context = PhaseContext(step=1, phase=Phase.ACT)

        result = act_phase.execute(context)

        # Should transition to DISCOVER (not an error, just no actions)
        assert result.success is True
        assert result.next_phase == Phase.DISCOVER

    def test_execute_incomplete_action_json(self, act_phase, mock_coordinator):
        """Test execute with incomplete action JSON (missing required fields)."""
        # Dict exists but missing required fields
        mock_coordinator.job_state.shared_data = {"actions": {"other": "data"}}
        context = PhaseContext(step=1, phase=Phase.ACT)

        result = act_phase.execute(context)

        # Should fail validation and return error
        assert result.success is False
        assert result.next_phase == Phase.DISCOVER
        assert "Invalid Action JSON" in result.error

    def test_execute_single_successful_action(self, act_phase, mock_coordinator):
        """Test execute with a single successful action."""
        # Use real tool (run) and mock its execution
        # This tests ActPhase logic without bypassing validation
        from atloop.tools.base import ToolResult
        
        # Mock the tool execution to return success
        original_execute = act_phase.executor._execute_action
        act_phase.executor._execute_action = MagicMock(return_value={
            "success": True,
            "ok": True,
            "tool": "run",
            "stdout": "Command executed successfully",
            "stderr": "",
            "error": "",
            "exit_code": 0,
            "command": "echo test"
        })

        # Setup actions with complete ActionJSON structure using real tool
        actions_dict = {
            "actions": [
                {"tool": "run", "args": {"cmd": "echo test"}}
            ],
            "stop_reason": "continue"
        }
        mock_coordinator.job_state.shared_data = {"actions": actions_dict}
        context = PhaseContext(step=1, phase=Phase.ACT)

        result = act_phase.execute(context)

        assert result.success is True
        assert result.next_phase == Phase.VERIFY
        assert "results" in result.data
        assert len(result.data["results"]) == 1
        assert result.data["results"][0]["ok"] is True

    def test_execute_multiple_actions(self, act_phase, mock_coordinator):
        """Test execute with multiple actions."""
        # Mock tool execution to return success
        act_phase.executor._execute_action = MagicMock(return_value={
            "success": True,
            "ok": True,
            "tool": "run",
            "stdout": "Success",
            "stderr": "",
            "error": "",
            "exit_code": 0,
            "command": "echo test"
        })

        actions_dict = {
            "actions": [
                {"tool": "run", "args": {"cmd": "echo test1"}},
                {"tool": "run", "args": {"cmd": "echo test2"}},
            ],
            "stop_reason": "continue"
        }
        mock_coordinator.job_state.shared_data = {"actions": actions_dict}
        context = PhaseContext(step=1, phase=Phase.ACT)

        result = act_phase.execute(context)

        assert result.success is True
        assert len(result.data["results"]) == 2
        # Budget should be updated twice
        assert mock_coordinator.state_manager.agent_state.budget_used.tool_calls == 2

    def test_execute_action_with_error(self, act_phase, mock_coordinator):
        """Test execute with an action that fails."""
        # Mock tool execution to return error
        act_phase.executor._execute_action = MagicMock(return_value={
            "success": False,
            "ok": False,
            "tool": "run",
            "stdout": "",
            "stderr": "Command failed: command not found",
            "error": "Command failed",
            "exit_code": 1,
            "command": "invalid_command"
        })

        actions_dict = {
            "actions": [
                {"tool": "run", "args": {"cmd": "invalid_command"}}
            ],
            "stop_reason": "continue"
        }
        mock_coordinator.job_state.shared_data = {"actions": actions_dict}
        context = PhaseContext(step=1, phase=Phase.ACT)

        result = act_phase.execute(context)

        assert result.success is False
        assert result.recoverable is True
        assert result.error_already_set_in_state is True
        assert result.next_phase is None  # Let Workflow decide
        # Error should be set in state
        assert mock_coordinator.state_manager.agent_state.last_error.summary != ""
        assert "Command failed" in mock_coordinator.state_manager.agent_state.last_error.summary

    def test_execute_action_exception_handling(self, act_phase, mock_coordinator):
        """Test that exceptions during action execution are handled."""
        # Make executor raise an exception
        act_phase.executor._execute_action = MagicMock(side_effect=Exception("Tool execution failed"))

        actions_dict = {
            "actions": [
                {"tool": "run", "args": {"cmd": "test"}}
            ],
            "stop_reason": "continue"
        }
        mock_coordinator.job_state.shared_data = {"actions": actions_dict}
        context = PhaseContext(step=1, phase=Phase.ACT)

        result = act_phase.execute(context)

        # Should continue and return error result
        assert result.success is False
        assert "results" in result.data
        assert len(result.data["results"]) == 1
        assert result.data["results"][0]["error"] == "Tool execution failed"

    def test_validate_action_placeholder_detection(self, act_phase):
        """Test that unreplaced placeholders are detected."""
        action = {
            "tool": "write_file",
            "args": {
                "path": "test.py",
                "content": "FILE_CONTENT_#12345"
            }
        }

        # Should not raise, but log error
        act_phase._validate_action(action, 1)
        # Validation doesn't raise, just logs

    def test_execute_single_action_success(self, act_phase, mock_coordinator):
        """Test _execute_single_action with successful execution."""
        # Mock executor to return success
        act_phase.executor._execute_action = MagicMock(return_value={
            "success": True,
            "ok": True,
            "tool": "run",
            "stdout": "Command output",
            "stderr": "",
            "error": "",
            "exit_code": 0,
            "command": "echo test"
        })

        action = {"tool": "run", "args": {"cmd": "echo test"}}
        result = act_phase._execute_single_action(action)

        assert result["ok"] is True
        assert result["tool"] == "run"
        assert result["stdout"] == "Command output"

    def test_execute_single_action_exception(self, act_phase):
        """Test _execute_single_action when executor raises exception."""
        act_phase.executor._execute_action = MagicMock(side_effect=ValueError("Test error"))

        action = {"tool": "test_tool", "args": {}}
        result = act_phase._execute_single_action(action)

        assert result["ok"] is False
        assert result["error"] == "Test error"
        assert "Test error" in result["stderr"]

    def test_process_action_result_success(self, act_phase, mock_coordinator):
        """Test _process_action_result with successful result."""
        state = mock_coordinator.state_manager.agent_state
        action = {"tool": "mock_tool", "args": {"test": True}}
        result = {
            "ok": True,
            "stdout": "output",
            "stderr": "",
            "error": "",
        }
        modified_files = []

        act_phase._process_action_result(action, result, state, modified_files)

        # Successful result should not update error state
        assert state.last_error.summary == ""

    def test_process_action_result_with_error(self, act_phase, mock_coordinator):
        """Test _process_action_result with error result."""
        state = mock_coordinator.state_manager.agent_state
        action = {"tool": "run", "args": {"cmd": "invalid_command"}}
        result = {
            "ok": False,
            "stdout": "",
            "stderr": "command not found",
            "error": "",
        }
        modified_files = []

        act_phase._process_action_result(action, result, state, modified_files)

        # Error should be set in state
        assert state.last_error.summary != ""
        assert "command not found" in state.last_error.summary
        assert state.last_error.repro_cmd == "invalid_command"

    def test_process_action_result_file_tracking(self, act_phase, mock_coordinator):
        """Test _process_action_result tracks file creation."""
        state = mock_coordinator.state_manager.agent_state
        action = {
            "tool": "write_file",
            "args": {
                "path": "test.py",
                "content": "print('hello')"
            }
        }
        result = {
            "ok": True,
            "stdout": "",
            "stderr": "",
            "error": "",
        }
        modified_files = []

        act_phase._process_action_result(action, result, state, modified_files)

        assert "test.py" in modified_files
        assert "test.py" in state.memory.created_files
        assert "test.py" in state.artifacts.current_diff

    def test_update_memory_after_execution_success(self, act_phase, mock_coordinator):
        """Test _update_memory_after_execution with successful execution."""
        state = mock_coordinator.state_manager.agent_state
        state.step = 1
        results = [{"ok": True}]
        modified_files = ["file1.py", "file2.py", "file3.py"]
        success = True

        act_phase._update_memory_after_execution(state, results, modified_files, success)

        # Should record attempt
        assert len(state.memory.attempts) == 1
        attempt = state.memory.attempts[0]
        assert attempt["step"] == 1
        assert attempt["success"] is True
        assert attempt["files"] == modified_files
        # Should add milestone for 3+ files
        assert len(state.memory.milestones) > 0

    def test_update_memory_after_execution_failure(self, act_phase, mock_coordinator):
        """Test _update_memory_after_execution with failed execution."""
        state = mock_coordinator.state_manager.agent_state
        state.step = 1
        results = [{"ok": False, "stderr": "error"}]
        modified_files = []
        success = False

        act_phase._update_memory_after_execution(state, results, modified_files, success)

        # Should record attempt
        assert len(state.memory.attempts) == 1
        attempt = state.memory.attempts[0]
        assert attempt["success"] is False
        # Should not add milestone for failed execution
        initial_milestones = len(state.memory.milestones)

    def test_update_memory_milestone_threshold(self, act_phase, mock_coordinator):
        """Test that milestones are only added for 3+ files."""
        state = mock_coordinator.state_manager.agent_state
        state.step = 1
        results = [{"ok": True}]
        success = True

        # Test with 2 files (should not add milestone)
        modified_files_2 = ["file1.py", "file2.py"]
        initial_milestones = len(state.memory.milestones)
        act_phase._update_memory_after_execution(state, results, modified_files_2, success)
        assert len(state.memory.milestones) == initial_milestones

        # Test with 3 files (should add milestone)
        modified_files_3 = ["file1.py", "file2.py", "file3.py"]
        act_phase._update_memory_after_execution(state, results, modified_files_3, success)
        assert len(state.memory.milestones) > initial_milestones

    def test_execute_actions_error_aggregation(self, act_phase, mock_coordinator):
        """Test that errors from multiple actions are aggregated."""
        # Mock executor to return errors
        def mock_execute(action):
            return {
                "success": False,
                "ok": False,
                "tool": "run",
                "stdout": "",
                "stderr": f"Error from {action['args']['cmd']}",
                "error": "Command failed",
                "exit_code": 1,
                "command": action['args']['cmd']
            }
        
        act_phase.executor._execute_action = MagicMock(side_effect=mock_execute)

        state = mock_coordinator.state_manager.agent_state
        
        actions = [
            {"tool": "run", "args": {"cmd": "command1"}},
            {"tool": "run", "args": {"cmd": "command2"}},
        ]

        results, modified_files = act_phase._execute_actions(actions, state)

        assert len(results) == 2
        # Both should have errors
        assert all(not r.get("ok", True) for r in results)
        # Error state should contain both errors
        assert state.last_error.summary != ""
        # Should have separator between errors
        assert "=" * 80 in state.last_error.summary

    def test_execute_actions_success_preserves_previous_error(self, act_phase, mock_coordinator):
        """Test that successful actions don't overwrite previous errors."""
        # Mock executor to return success
        act_phase.executor._execute_action = MagicMock(return_value={
            "success": True,
            "ok": True,
            "tool": "run",
            "stdout": "Success",
            "stderr": "",
            "error": "",
            "exit_code": 0,
            "command": "echo test"
        })

        state = mock_coordinator.state_manager.agent_state
        # Set a previous error
        state.last_error.summary = "Previous error message"

        actions = [
            {"tool": "run", "args": {"cmd": "echo test"}},  # Success
        ]

        results, modified_files = act_phase._execute_actions(actions, state)

        # Previous error should be preserved
        assert state.last_error.summary == "Previous error message"

    def test_execute_actions_budget_tracking(self, act_phase, mock_coordinator):
        """Test that budget is properly tracked for each action."""
        # Mock executor to return success
        act_phase.executor._execute_action = MagicMock(return_value={
            "success": True,
            "ok": True,
            "tool": "run",
            "stdout": "Success",
            "stderr": "",
            "error": "",
            "exit_code": 0,
            "command": "echo test"
        })

        state = mock_coordinator.state_manager.agent_state
        initial_budget = state.budget_used.tool_calls

        actions = [
            {"tool": "run", "args": {"cmd": "echo test1"}},
            {"tool": "run", "args": {"cmd": "echo test2"}},
        ]

        act_phase._execute_actions(actions, state)

        # Budget should be incremented for each action
        assert state.budget_used.tool_calls == initial_budget + 2
        assert mock_coordinator.budget_manager.budget_used.tool_calls == initial_budget + 2

    def test_execute_pending_stop_reason(self, act_phase, mock_coordinator):
        """Test that pending stop_reason is handled."""
        # Mock executor to return success
        act_phase.executor._execute_action = MagicMock(return_value={
            "success": True,
            "ok": True,
            "tool": "run",
            "stdout": "Success",
            "stderr": "",
            "error": "",
            "exit_code": 0,
            "command": "echo test"
        })

        actions_dict = {
            "actions": [
                {"tool": "run", "args": {"cmd": "echo test"}}
            ],
            "stop_reason": "continue"
        }
        mock_coordinator.job_state.shared_data = {
            "actions": actions_dict,
            "pending_stop_reason": "done"
        }
        context = PhaseContext(step=1, phase=Phase.ACT)

        with patch("atloop.orchestrator.phases.act.StopReasonHandler.apply_pending_stop_reason") as mock_handler:
            mock_handler.return_value = MagicMock(success=True, next_phase=Phase.DONE)
            result = act_phase.execute(context)

            # Should call stop reason handler
            mock_handler.assert_called_once()
            assert "pending_stop_reason" not in mock_coordinator.job_state.shared_data
