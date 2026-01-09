"""Tests for tools module - ToolRegistry, ToolExecutor, BaseTool, ToolResult."""

import logging
from typing import Any, Dict
from unittest.mock import MagicMock, Mock

import pytest

from atloop.orchestrator.coordinator import WorkflowCoordinator
from atloop.orchestrator.executor.result_adapter import ResultAdapter
from atloop.orchestrator.executor.tool_executor import ToolExecutor
from atloop.tools.base import BaseTool, ToolResult
from atloop.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


# Mock tool for testing
class MockTool(BaseTool):
    """Mock tool for testing."""

    def __init__(self, sandbox=None, skill_loader=None):
        self.sandbox = sandbox
        self.skill_loader = skill_loader

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "Mock tool for testing"

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mock tool."""
        if args.get("fail"):
            return ToolResult(
                ok=False,
                stdout="",
                stderr="Mock tool failed",
                meta={"error": "test_failure"},
            )
        return ToolResult(
            ok=True,
            stdout="Mock output",
            stderr="",
            meta={"exitCode": 0, "test": True},
        )

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, str | None]:
        """Validate mock tool arguments."""
        if "invalid" in args:
            return False, "Invalid argument detected"
        return True, None


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_tool_result_success(self):
        """Test successful ToolResult creation."""
        result = ToolResult(ok=True, stdout="output", stderr="", meta={"key": "value"})
        assert result.ok is True
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.meta == {"key": "value"}

    def test_tool_result_failure(self):
        """Test failed ToolResult creation."""
        result = ToolResult(ok=False, stdout="", stderr="error", meta={"error": "test"})
        assert result.ok is False
        assert result.stderr == "error"

    def test_tool_result_repr(self):
        """Test ToolResult string representation."""
        result = ToolResult(ok=True, stdout="test", stderr="", meta={})
        repr_str = repr(result)
        assert "✓" in repr_str or "ToolResult" in repr_str
        assert "stdout_len" in repr_str


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_registry_initialization(self):
        """Test ToolRegistry initialization with auto-discovery."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)
        assert registry.sandbox == mock_sandbox
        assert isinstance(registry.tools, dict)
        # Should have discovered and registered tools
        assert len(registry.tools) > 0

    def test_registry_register_tool(self):
        """Test manual tool registration."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)
        initial_count = len(registry.tools)

        tool = MockTool()
        registry.register(tool)

        assert len(registry.tools) == initial_count + 1
        assert registry.tools["mock_tool"] == tool

    def test_registry_get_tool(self):
        """Test getting a tool by name."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)
        tool = MockTool()
        registry.register(tool)

        retrieved = registry.get("mock_tool")
        assert retrieved == tool

    def test_registry_get_nonexistent_tool(self):
        """Test getting a non-existent tool returns None."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)
        assert registry.get("nonexistent") is None

    def test_registry_list_tools(self):
        """Test listing all registered tools."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)
        tool = MockTool()
        registry.register(tool)

        tools = registry.list_tools()
        assert isinstance(tools, list)
        assert "mock_tool" in tools

    def test_registry_execute_success(self):
        """Test successful tool execution."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)
        tool = MockTool()
        registry.register(tool)

        result = registry.execute("mock_tool", {"test": True})
        assert isinstance(result, ToolResult)
        assert result.ok is True
        assert result.stdout == "Mock output"

    def test_registry_execute_failure(self):
        """Test tool execution failure."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)
        tool = MockTool()
        registry.register(tool)

        result = registry.execute("mock_tool", {"fail": True})
        assert isinstance(result, ToolResult)
        assert result.ok is False
        assert "failed" in result.stderr.lower()

    def test_registry_execute_unknown_tool(self):
        """Test execution of unknown tool returns error ToolResult."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)

        result = registry.execute("unknown_tool", {})
        assert isinstance(result, ToolResult)
        assert result.ok is False
        assert "Unknown tool" in result.stderr
        assert result.meta.get("tool") == "unknown_tool"

    def test_registry_execute_invalid_args(self):
        """Test execution with invalid arguments."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)
        tool = MockTool()
        registry.register(tool)

        result = registry.execute("mock_tool", {"invalid": True})
        assert isinstance(result, ToolResult)
        assert result.ok is False
        assert "Invalid argument" in result.stderr

    def test_registry_with_skill_loader(self):
        """Test registry initialization with skill_loader."""
        mock_sandbox = MagicMock()
        mock_skill_loader = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox, skill_loader=mock_skill_loader)
        assert registry.skill_loader == mock_skill_loader


class TestToolExecutor:
    """Tests for ToolExecutor."""

    @pytest.fixture
    def mock_coordinator(self):
        """Create a mock WorkflowCoordinator."""
        coordinator = MagicMock(spec=WorkflowCoordinator)
        coordinator.tool_runtime = MagicMock()
        coordinator.tool_runtime.registry = ToolRegistry(sandbox=MagicMock())
        return coordinator

    @pytest.fixture
    def executor(self, mock_coordinator):
        """Create a ToolExecutor instance."""
        return ToolExecutor(mock_coordinator)

    def test_executor_initialization(self, executor):
        """Test ToolExecutor initialization."""
        assert executor.coordinator is not None

    def test_execute_actions_single_success(self, executor):
        """Test executing a single successful action."""
        # Register mock tool
        tool = MockTool()
        executor.coordinator.tool_runtime.registry.register(tool)

        actions = [{"tool": "mock_tool", "args": {"test": True}}]
        results = executor.execute_actions(actions)

        assert len(results) == 1
        result = results[0]
        assert result["success"] is True
        assert result["tool"] == "mock_tool"
        assert result["ok"] is True
        assert result["stdout"] == "Mock output"
        assert "exit_code" in result

    def test_execute_actions_multiple(self, executor):
        """Test executing multiple actions."""
        tool = MockTool()
        executor.coordinator.tool_runtime.registry.register(tool)

        actions = [
            {"tool": "mock_tool", "args": {"test": True}},
            {"tool": "mock_tool", "args": {"test": True}},
        ]
        results = executor.execute_actions(actions)

        assert len(results) == 2
        assert all(r["success"] for r in results)

    def test_execute_actions_failure(self, executor):
        """Test executing an action that fails."""
        tool = MockTool()
        executor.coordinator.tool_runtime.registry.register(tool)

        actions = [{"tool": "mock_tool", "args": {"fail": True}}]
        results = executor.execute_actions(actions)

        assert len(results) == 1
        result = results[0]
        assert result["success"] is False
        assert result["ok"] is False
        assert "error" in result or result["stderr"]

    def test_execute_actions_unknown_tool(self, executor):
        """Test executing action with unknown tool."""
        actions = [{"tool": "unknown_tool", "args": {}}]
        results = executor.execute_actions(actions)

        assert len(results) == 1
        result = results[0]
        assert result["success"] is False
        assert result["ok"] is False

    def test_execute_actions_exception_handling(self, executor):
        """Test exception handling during action execution."""
        # Make registry.execute raise an exception
        executor.coordinator.tool_runtime.registry.execute = Mock(
            side_effect=Exception("Test exception")
        )

        actions = [{"tool": "test_tool", "args": {}}]
        results = executor.execute_actions(actions)

        assert len(results) == 1
        result = results[0]
        assert result["success"] is False
        assert "error" in result

    def test_build_action_result_from_tool_result(self, executor):
        """Test ResultAdapter._from_tool_result method."""
        tool_result = ToolResult(
            ok=True,
            stdout="test output",
            stderr="",
            meta={"exitCode": 0, "test": True},
        )

        result = ResultAdapter.to_action_result("test_tool", {"arg": "value"}, tool_result)

        assert result["success"] is True
        assert result["tool"] == "test_tool"
        assert result["args"] == {"arg": "value"}
        assert result["ok"] is True
        assert result["stdout"] == "test output"
        assert result["exit_code"] == 0
        assert "result" in result
        assert result["result"]["meta"]["test"] is True

    def test_build_action_result_with_exit_code_in_meta(self, executor):
        """Test ResultAdapter with exit_code in meta."""
        tool_result = ToolResult(
            ok=False,
            stdout="",
            stderr="error message",
            meta={"exit_code": 1},
        )

        result = ResultAdapter.to_action_result("test_tool", {}, tool_result)

        assert result["success"] is False
        assert result["exit_code"] == 1
        assert result["error"] == "error message"

    def test_build_action_result_from_dict(self, executor):
        """Test ResultAdapter._from_dict_like method."""
        result_dict = {
            "ok": True,
            "success": True,
            "stdout": "output",
            "stderr": "",
            "meta": {"exitCode": 0},
        }

        result = ResultAdapter.to_action_result("test_tool", {"arg": 1}, result_dict)

        assert result["success"] is True
        assert result["tool"] == "test_tool"
        assert result["args"] == {"arg": 1}
        assert result["ok"] is True
        assert result["stdout"] == "output"
        assert result["exit_code"] == 0

    def test_build_error_result(self, executor):
        """Test ResultAdapter._from_error method."""
        result = ResultAdapter._from_error("test_tool", {"arg": "value"}, "Error message")

        assert result["success"] is False
        assert result["tool"] == "test_tool"
        assert result["args"] == {"arg": "value"}
        assert result["ok"] is False
        assert result["error"] == "Error message"
        assert result["stderr"] == "Error message"
        assert result["exit_code"] == -1

    def test_execute_action_with_dict_result(self, executor):
        """Test _execute_action with dict-like result (defensive path)."""
        # Mock registry to return a dict
        executor.coordinator.tool_runtime.registry.execute = Mock(
            return_value={"ok": True, "stdout": "dict output", "stderr": "", "meta": {}}
        )

        action = {"tool": "test_tool", "args": {}}
        result = executor._execute_action(action)

        assert result["success"] is True
        assert result["stdout"] == "dict output"

    def test_execute_action_with_to_dict_method(self, executor):
        """Test _execute_action with object having to_dict method (defensive path)."""

        class DictLikeResult:
            def to_dict(self):
                return {"ok": True, "stdout": "to_dict output", "stderr": "", "meta": {}}

        executor.coordinator.tool_runtime.registry.execute = Mock(return_value=DictLikeResult())

        action = {"tool": "test_tool", "args": {}}
        result = executor._execute_action(action)

        assert result["success"] is True
        assert result["stdout"] == "to_dict output"

    def test_execute_action_unexpected_type(self, executor):
        """Test _execute_action with unexpected result type."""
        executor.coordinator.tool_runtime.registry.execute = Mock(return_value=12345)

        action = {"tool": "test_tool", "args": {}}
        result = executor._execute_action(action)

        assert result["success"] is False
        assert "Unexpected result type" in result["error"]


class TestToolDiscovery:
    """Tests for automatic tool discovery."""

    def test_auto_discovery_registers_tools(self):
        """Test that auto-discovery finds and registers tools."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)

        # Should have discovered tools from atloop/tools/
        tools = registry.list_tools()
        assert len(tools) > 0

        # Check for expected tools
        expected_tools = ["run", "read_file", "write_file"]
        for tool_name in expected_tools:
            assert tool_name in tools, f"Expected tool {tool_name} not found"

    def test_auto_discovery_skill_tool_registered(self):
        """Test that skill tool is discovered and registered."""
        mock_sandbox = MagicMock()
        mock_skill_loader = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox, skill_loader=mock_skill_loader)

        tools = registry.list_tools()
        assert "skill" in tools

    def test_auto_discovery_read_skill_file_registered(self):
        """Test that read_skill_file tool is discovered."""
        mock_sandbox = MagicMock()
        mock_skill_loader = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox, skill_loader=mock_skill_loader)

        tools = registry.list_tools()
        assert "read_skill_file" in tools


class TestToolIntegration:
    """Integration tests for tool execution flow."""

    def test_full_tool_execution_flow(self):
        """Test complete flow: registry -> executor -> result."""
        # Setup
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)
        tool = MockTool()
        registry.register(tool)

        mock_coordinator = MagicMock(spec=WorkflowCoordinator)
        mock_coordinator.tool_runtime = MagicMock()
        mock_coordinator.tool_runtime.registry = registry

        executor = ToolExecutor(mock_coordinator)

        # Execute
        actions = [{"tool": "mock_tool", "args": {"test": True}}]
        results = executor.execute_actions(actions)

        # Verify
        assert len(results) == 1
        result = results[0]
        assert result["success"] is True
        assert result["tool"] == "mock_tool"
        assert result["ok"] is True
        assert result["stdout"] == "Mock output"
        assert "exit_code" in result
        assert "result" in result
        assert isinstance(result["result"], dict)

    def test_tool_result_meta_preserved(self):
        """Test that tool result meta is preserved through execution."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)

        # Create tool that returns meta
        class MetaTool(BaseTool):
            @property
            def name(self) -> str:
                return "meta_tool"

            @property
            def description(self) -> str:
                return "Tool with meta"

            def execute(self, args: Dict[str, Any]) -> ToolResult:
                return ToolResult(
                    ok=True,
                    stdout="output",
                    stderr="",
                    meta={"custom_key": "custom_value", "exitCode": 0},
                )

        tool = MetaTool()
        registry.register(tool)

        mock_coordinator = MagicMock(spec=WorkflowCoordinator)
        mock_coordinator.tool_runtime = MagicMock()
        mock_coordinator.tool_runtime.registry = registry

        executor = ToolExecutor(mock_coordinator)
        actions = [{"tool": "meta_tool", "args": {}}]
        results = executor.execute_actions(actions)

        assert len(results) == 1
        result = results[0]
        assert result["result"]["meta"]["custom_key"] == "custom_value"
        assert result["exit_code"] == 0

    def test_tool_result_empty_meta(self):
        """Test handling of empty meta dict."""
        mock_sandbox = MagicMock()
        registry = ToolRegistry(sandbox=mock_sandbox)

        class EmptyMetaTool(BaseTool):
            @property
            def name(self) -> str:
                return "empty_meta_tool"

            @property
            def description(self) -> str:
                return "Tool with empty meta"

            def execute(self, args: Dict[str, Any]) -> ToolResult:
                return ToolResult(ok=True, stdout="output", stderr="", meta={})

        tool = EmptyMetaTool()
        registry.register(tool)

        mock_coordinator = MagicMock(spec=WorkflowCoordinator)
        mock_coordinator.tool_runtime = MagicMock()
        mock_coordinator.tool_runtime.registry = registry

        executor = ToolExecutor(mock_coordinator)
        actions = [{"tool": "empty_meta_tool", "args": {}}]
        results = executor.execute_actions(actions)

        assert len(results) == 1
        result = results[0]
        assert result["success"] is True
        assert result["exit_code"] == -1  # Default when no exitCode in meta
        assert result["result"]["meta"] == {}
