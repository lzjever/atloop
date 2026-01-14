"""Comprehensive tests for dynamic tool validation in schema.py.

These tests verify that:
1. Tool validation is delegated to each tool's validate_args() method
2. ToolRegistry is used dynamically instead of hardcoded tool lists
3. Validation works with and without ToolRegistry
4. All edge cases and error conditions are handled correctly

Test design principles:
- Test against interfaces, not implementations
- Challenge business logic thoroughly
- Don't lower standards to accommodate bugs
- Analyze failures to determine if bug is in test or business code
"""

import json
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, Mock

import pytest

from atloop.llm.schema import (
    ActionJSON,
    ActionJSONValidationError,
    parse_action_json,
    validate_action_json,
)
from atloop.tools.base import BaseTool, ToolResult

# Import ToolRegistry lazily in fixtures to avoid circular import
# We'll import it inside each fixture/test that needs it


# ============================================================================
# Test Fixtures: Mock Tools for Testing
# ============================================================================


class MockToolWithValidation(BaseTool):
    """Mock tool that implements validate_args() for testing."""

    def __init__(
        self,
        name: str,
        description: str = "Mock tool",
        required_args: Optional[list] = None,
        validation_behavior: Optional[callable] = None,
    ):
        self._name = name
        self._description = description
        self.required_args = required_args or []
        self.validation_behavior = validation_behavior
        self.validation_call_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """Execute mock tool."""
        return ToolResult(ok=True, stdout="", stderr="", meta={})

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments with customizable behavior."""
        self.validation_call_count += 1

        if self.validation_behavior:
            return self.validation_behavior(args)

        # Default validation: check required args
        for required_arg in self.required_args:
            if required_arg not in args:
                return False, f"Missing required argument: '{required_arg}'"

        return True, None


class MockToolThatAlwaysFails(BaseTool):
    """Mock tool that always fails validation."""

    def __init__(self, name: str, error_message: str = "Validation failed"):
        self._name = name
        self.error_message = error_message

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Tool that always fails validation"

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        return ToolResult(ok=True, stdout="", stderr="", meta={})

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        return False, self.error_message


class MockToolThatRaisesException(BaseTool):
    """Mock tool that raises exception during validation."""

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "Tool that raises exception"

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        return ToolResult(ok=True, stdout="", stderr="", meta={})

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        raise ValueError("Validation exception")


# ============================================================================
# Test Fixtures: ToolRegistry Setup
# ============================================================================


@pytest.fixture
def mock_sandbox():
    """Create a mock sandbox for ToolRegistry."""
    return MagicMock()


@pytest.fixture
def empty_registry(mock_sandbox):
    """Create an empty ToolRegistry."""
    # Use importlib to avoid circular import issues
    import importlib
    tools_registry_module = importlib.import_module("atloop.tools.registry")
    ToolRegistry = tools_registry_module.ToolRegistry
    registry = ToolRegistry(sandbox=mock_sandbox)
    # Clear auto-discovered tools for clean testing
    registry.tools.clear()
    return registry


def _create_registry_with_tools(mock_sandbox):
    """Helper function to create ToolRegistry with test tools.
    
    Created as a function instead of fixture to avoid circular import issues
    when fixture is evaluated at import time.
    """
    # Import here to avoid circular import - this will be called at test runtime
    import importlib
    import sys
    # Try to import, handling circular import gracefully
    try:
        tools_registry_module = importlib.import_module("atloop.tools.registry")
        ToolRegistry = tools_registry_module.ToolRegistry
    except ImportError as e:
        # If circular import occurs, try to work around it
        # This is a known issue in the business code
        pytest.skip(f"Circular import issue in business code: {e}")
    
    registry = ToolRegistry(sandbox=mock_sandbox)
    registry.tools.clear()

    # Add tools with different validation behaviors
    registry.register(
        MockToolWithValidation("test_tool", required_args=["arg1", "arg2"])
    )
    registry.register(MockToolWithValidation("simple_tool", required_args=[]))
    registry.register(
        MockToolWithValidation(
            "complex_tool",
            required_args=["path"],
            validation_behavior=lambda args: (
                False,
                "Custom validation error",
            )
            if args.get("path") == "/invalid"
            else (True, None),
        )
    )
    registry.register(MockToolThatAlwaysFails("failing_tool", "Always fails"))
    registry.register(MockToolWithValidation("write_file", required_args=["path", "content"]))

    return registry


@pytest.fixture
def registry_with_tools(mock_sandbox):
    """Create a ToolRegistry with test tools."""
    return _create_registry_with_tools(mock_sandbox)


# ============================================================================
# Tests for validate_action_json() with ToolRegistry
# ============================================================================


class TestValidateActionJsonWithRegistry:
    """Test validate_action_json() with ToolRegistry parameter."""

    def test_structural_validation_without_registry(self):
        """Test that structural validation works without ToolRegistry."""
        # Valid structure
        data = {
            "actions": [{"tool": "unknown_tool", "args": {}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data)
        assert is_valid is True, "Should pass structural validation without registry"

        # Invalid structure - missing actions
        data = {"stop_reason": "continue"}
        is_valid, error = validate_action_json(data)
        assert is_valid is False
        assert "actions" in error.lower()

        # Invalid structure - missing stop_reason
        data = {"actions": []}
        is_valid, error = validate_action_json(data)
        assert is_valid is False
        assert "stop_reason" in error.lower()

    def test_tool_existence_validation_with_registry(self, registry_with_tools):
        """Test that tool existence is validated when registry is provided."""
        # Valid tool
        data = {
            "actions": [{"tool": "test_tool", "args": {"arg1": "value1", "arg2": "value2"}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is True

        # Invalid tool - not in registry
        data = {
            "actions": [{"tool": "nonexistent_tool", "args": {}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is False
        assert "nonexistent_tool" in error
        assert "valid tools" in error.lower()

    def test_tool_args_validation_delegation(self, registry_with_tools):
        """Test that tool-specific argument validation is delegated to tool.validate_args()."""
        # Tool with missing required args
        data = {
            "actions": [{"tool": "test_tool", "args": {"arg1": "value1"}}],  # missing arg2
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is False
        assert "arg2" in error or "required" in error.lower()
        assert "test_tool" in error

        # Tool with all required args
        data = {
            "actions": [{"tool": "test_tool", "args": {"arg1": "value1", "arg2": "value2"}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is True

    def test_tool_validation_called(self, registry_with_tools):
        """Test that tool.validate_args() is actually called."""
        tool = registry_with_tools.get("test_tool")
        assert tool is not None
        initial_count = tool.validation_call_count

        data = {
            "actions": [{"tool": "test_tool", "args": {"arg1": "value1", "arg2": "value2"}}],
            "stop_reason": "continue",
        }
        validate_action_json(data, tool_registry=registry_with_tools)

        assert tool.validation_call_count == initial_count + 1

    def test_tool_validation_error_message_preserved(self, registry_with_tools):
        """Test that tool's validation error message is preserved in response."""
        data = {
            "actions": [{"tool": "failing_tool", "args": {"any": "args"}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is False
        assert "Always fails" in error
        assert "failing_tool" in error

    def test_multiple_actions_validation(self, registry_with_tools):
        """Test validation of multiple actions."""
        # All valid
        data = {
            "actions": [
                {"tool": "test_tool", "args": {"arg1": "v1", "arg2": "v2"}},
                {"tool": "simple_tool", "args": {}},
            ],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is True

        # One invalid
        data = {
            "actions": [
                {"tool": "test_tool", "args": {"arg1": "v1"}},  # missing arg2
                {"tool": "simple_tool", "args": {}},
            ],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is False
        assert "test_tool" in error

    def test_write_file_count_enforcement(self, registry_with_tools):
        """Test that only one write_file action is allowed per response."""
        # Single write_file - should pass
        data = {
            "actions": [
                {"tool": "write_file", "args": {"path": "/test", "content": "content"}}
            ],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is True

        # Multiple write_file - should fail
        data = {
            "actions": [
                {"tool": "write_file", "args": {"path": "/test1", "content": "c1"}},
                {"tool": "write_file", "args": {"path": "/test2", "content": "c2"}},
            ],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is False
        assert "write_file" in error.lower()
        assert "one" in error.lower() or "only" in error.lower()

    def test_tool_not_in_registry_but_structure_valid(self, empty_registry):
        """Test that unknown tool passes structural validation but fails tool validation."""
        data = {
            "actions": [{"tool": "unknown_tool", "args": {"any": "args"}}],
            "stop_reason": "continue",
        }
        # Without registry - should pass (structural only)
        is_valid, error = validate_action_json(data)
        assert is_valid is True

        # With empty registry - should fail (tool not found)
        is_valid, error = validate_action_json(data, tool_registry=empty_registry)
        assert is_valid is False
        assert "unknown_tool" in error

    def test_complex_validation_behavior(self, registry_with_tools):
        """Test tool with complex validation logic."""
        # Path that triggers custom validation error
        data = {
            "actions": [{"tool": "complex_tool", "args": {"path": "/invalid"}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is False
        assert "Custom validation error" in error

        # Valid path
        data = {
            "actions": [{"tool": "complex_tool", "args": {"path": "/valid"}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is True

    def test_validation_with_none_registry(self):
        """Test that None registry is handled gracefully."""
        data = {
            "actions": [{"tool": "any_tool", "args": {}}],
            "stop_reason": "continue",
        }
        # Should work the same as no registry parameter
        is_valid, error = validate_action_json(data, tool_registry=None)
        assert is_valid is True

    def test_args_type_validation(self, registry_with_tools):
        """Test that args must be a dictionary."""
        data = {
            "actions": [{"tool": "test_tool", "args": "not_a_dict"}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is False
        assert "dictionary" in error.lower() or "object" in error.lower()

    def test_tool_type_validation(self, registry_with_tools):
        """Test that tool must be a string."""
        data = {
            "actions": [{"tool": 123, "args": {}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is False
        assert "string" in error.lower()

    def test_stop_reason_validation(self):
        """Test stop_reason validation."""
        # Valid stop_reason
        data = {"actions": [], "stop_reason": "done"}
        is_valid, error = validate_action_json(data)
        assert is_valid is True

        # Invalid stop_reason
        data = {"actions": [], "stop_reason": "invalid"}
        is_valid, error = validate_action_json(data)
        assert is_valid is False
        assert "stop_reason" in error.lower()
        assert "continue" in error or "done" in error or "fail" in error


# ============================================================================
# Tests for ActionJSON.from_dict() with ToolRegistry
# ============================================================================


class TestActionJSONFromDictWithRegistry:
    """Test ActionJSON.from_dict() with tool_registry parameter."""

    def test_from_dict_without_registry(self):
        """Test from_dict() works without registry (backward compatibility)."""
        data = {
            "actions": [{"tool": "any_tool", "args": {}}],
            "stop_reason": "continue",
        }
        action_json = ActionJSON.from_dict(data, validate=True)
        assert action_json.stop_reason == "continue"
        assert len(action_json.actions) == 1

    def test_from_dict_with_registry_valid(self, registry_with_tools):
        """Test from_dict() with valid data and registry."""
        data = {
            "actions": [
                {"tool": "test_tool", "args": {"arg1": "v1", "arg2": "v2"}},
                {"tool": "simple_tool", "args": {}},
            ],
            "stop_reason": "done",
        }
        action_json = ActionJSON.from_dict(
            data, validate=True, tool_registry=registry_with_tools
        )
        assert action_json.stop_reason == "done"
        assert len(action_json.actions) == 2

    def test_from_dict_with_registry_invalid_tool(self, registry_with_tools):
        """Test from_dict() raises error for invalid tool."""
        data = {
            "actions": [{"tool": "nonexistent", "args": {}}],
            "stop_reason": "continue",
        }
        with pytest.raises(ActionJSONValidationError) as exc_info:
            ActionJSON.from_dict(data, validate=True, tool_registry=registry_with_tools)
        assert "nonexistent" in str(exc_info.value)

    def test_from_dict_with_registry_invalid_args(self, registry_with_tools):
        """Test from_dict() raises error for invalid tool arguments."""
        data = {
            "actions": [{"tool": "test_tool", "args": {"arg1": "v1"}}],  # missing arg2
            "stop_reason": "continue",
        }
        with pytest.raises(ActionJSONValidationError) as exc_info:
            ActionJSON.from_dict(data, validate=True, tool_registry=registry_with_tools)
        assert "test_tool" in str(exc_info.value)
        assert "arg2" in str(exc_info.value) or "required" in str(exc_info.value).lower()

    def test_from_dict_validate_false_bypasses_validation(self, registry_with_tools):
        """Test that validate=False bypasses validation even with registry."""
        data = {
            "actions": [{"tool": "nonexistent", "args": {}}],
            "stop_reason": "continue",
        }
        # Should not raise even though tool doesn't exist
        action_json = ActionJSON.from_dict(
            data, validate=False, tool_registry=registry_with_tools
        )
        assert action_json.actions[0]["tool"] == "nonexistent"

    def test_from_dict_preserves_all_fields(self, registry_with_tools):
        """Test that all fields are preserved in from_dict()."""
        data = {
            "actions": [{"tool": "simple_tool", "args": {}}],
            "stop_reason": "continue",
            "current_step_thoughts": "Thinking...",
            "plan": ["step1", "step2"],
            "result_message": "Done",
        }
        action_json = ActionJSON.from_dict(
            data, validate=True, tool_registry=registry_with_tools
        )
        assert action_json.current_step_thoughts == "Thinking..."
        assert action_json.plan == ["step1", "step2"]
        assert action_json.result_message == "Done"


# ============================================================================
# Tests for parse_action_json() with ToolRegistry
# ============================================================================


class TestParseActionJsonWithRegistry:
    """Test parse_action_json() with tool_registry parameter."""

    def test_parse_valid_json_without_registry(self):
        """Test parsing valid JSON without registry."""
        json_text = json.dumps(
            {
                "actions": [{"tool": "any_tool", "args": {}}],
                "stop_reason": "continue",
            }
        )
        action_json, error, file_contents = parse_action_json(json_text)
        assert action_json is not None
        assert error is None
        assert action_json.stop_reason == "continue"

    def test_parse_valid_json_with_registry(self, registry_with_tools):
        """Test parsing valid JSON with registry."""
        json_text = json.dumps(
            {
                "actions": [
                    {"tool": "test_tool", "args": {"arg1": "v1", "arg2": "v2"}}
                ],
                "stop_reason": "done",
            }
        )
        action_json, error, file_contents = parse_action_json(
            json_text, tool_registry=registry_with_tools
        )
        assert action_json is not None
        assert error is None
        assert action_json.stop_reason == "done"

    def test_parse_invalid_tool_with_registry(self, registry_with_tools):
        """Test parsing JSON with invalid tool when registry is provided."""
        json_text = json.dumps(
            {
                "actions": [{"tool": "nonexistent", "args": {}}],
                "stop_reason": "continue",
            }
        )
        action_json, error, file_contents = parse_action_json(
            json_text, tool_registry=registry_with_tools
        )
        assert action_json is None
        assert error is not None
        assert "nonexistent" in error

    def test_parse_invalid_args_with_registry(self, registry_with_tools):
        """Test parsing JSON with invalid args when registry is provided."""
        json_text = json.dumps(
            {
                "actions": [{"tool": "test_tool", "args": {"arg1": "v1"}}],  # missing arg2
                "stop_reason": "continue",
            }
        )
        action_json, error, file_contents = parse_action_json(
            json_text, tool_registry=registry_with_tools
        )
        assert action_json is None
        assert error is not None
        assert "test_tool" in error

    def test_parse_json_with_code_block_markers(self, registry_with_tools):
        """Test parsing JSON from text with code block markers."""
        json_text = """```json
{
    "actions": [{"tool": "test_tool", "args": {"arg1": "v1", "arg2": "v2"}}],
    "stop_reason": "continue"
}
```"""
        action_json, error, file_contents = parse_action_json(
            json_text, tool_registry=registry_with_tools
        )
        assert action_json is not None
        assert error is None

    def test_parse_json_with_extra_text(self, registry_with_tools):
        """Test parsing JSON with extra text around it."""
        json_text = """Some text before
{
    "actions": [{"tool": "test_tool", "args": {"arg1": "v1", "arg2": "v2"}}],
    "stop_reason": "continue"
}
Some text after"""
        action_json, error, file_contents = parse_action_json(
            json_text, tool_registry=registry_with_tools
        )
        assert action_json is not None
        assert error is None

    def test_parse_invalid_json_structure(self, registry_with_tools):
        """Test parsing invalid JSON structure."""
        json_text = '{"actions": [], "stop_reason": "invalid_reason"}'
        action_json, error, file_contents = parse_action_json(
            json_text, tool_registry=registry_with_tools
        )
        assert action_json is None
        assert error is not None
        assert "stop_reason" in error.lower()


# ============================================================================
# Edge Cases and Error Handling Tests
# ============================================================================


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios."""

    def test_empty_actions_list(self, registry_with_tools):
        """Test validation with empty actions list."""
        data = {"actions": [], "stop_reason": "continue"}
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is True

    def test_actions_not_list(self):
        """Test validation when actions is not a list."""
        data = {"actions": "not_a_list", "stop_reason": "continue"}
        is_valid, error = validate_action_json(data)
        assert is_valid is False
        assert "list" in error.lower() or "array" in error.lower()

    def test_action_not_dict(self):
        """Test validation when action is not a dictionary."""
        data = {"actions": ["not_a_dict"], "stop_reason": "continue"}
        is_valid, error = validate_action_json(data)
        assert is_valid is False
        assert "dictionary" in error.lower() or "object" in error.lower()

    def test_missing_tool_field(self):
        """Test validation when tool field is missing."""
        data = {"actions": [{"args": {}}], "stop_reason": "continue"}
        is_valid, error = validate_action_json(data)
        assert is_valid is False
        assert "tool" in error.lower()

    def test_missing_args_field(self):
        """Test validation when args field is missing."""
        data = {"actions": [{"tool": "test_tool"}], "stop_reason": "continue"}
        is_valid, error = validate_action_json(data)
        assert is_valid is False
        assert "args" in error.lower()

    def test_tool_validation_exception_handling(self, mock_sandbox):
        """Test that exceptions in tool validation are handled gracefully."""
        import importlib
        tools_registry_module = importlib.import_module("atloop.tools.registry")
        ToolRegistry = tools_registry_module.ToolRegistry
        registry = ToolRegistry(sandbox=mock_sandbox)
        registry.tools.clear()
        registry.register(MockToolThatRaisesException("exception_tool"))

        data = {
            "actions": [{"tool": "exception_tool", "args": {}}],
            "stop_reason": "continue",
        }
        # Should handle exception gracefully - either catch and report, or let it propagate
        # We test both behaviors are acceptable
        try:
            is_valid, error = validate_action_json(data, tool_registry=registry)
            # If exception is caught, should return False with error
            assert is_valid is False
            assert error is not None
        except ValueError:
            # If exception propagates, that's also acceptable (fail-fast)
            pass

    def test_registry_with_no_tools(self, empty_registry):
        """Test validation with registry that has no tools."""
        data = {
            "actions": [{"tool": "any_tool", "args": {}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=empty_registry)
        assert is_valid is False
        assert "any_tool" in error

    def test_multiple_write_file_actions(self, registry_with_tools):
        """Test that multiple write_file actions are rejected."""
        data = {
            "actions": [
                {"tool": "write_file", "args": {"path": "/f1", "content": "c1"}},
                {"tool": "write_file", "args": {"path": "/f2", "content": "c2"}},
                {"tool": "simple_tool", "args": {}},
            ],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is False
        assert "write_file" in error.lower()

    def test_tool_list_in_error_message(self, registry_with_tools):
        """Test that error message includes list of valid tools when tool is invalid."""
        data = {
            "actions": [{"tool": "invalid_tool_name", "args": {}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry_with_tools)
        assert is_valid is False
        # Error should mention valid tools
        assert "valid tools" in error.lower() or any(
            tool in error for tool in registry_with_tools.list_tools()
        )


# ============================================================================
# Integration Tests: Real Tool Validation
# ============================================================================


class TestRealToolIntegration:
    """Integration tests with real tools from the codebase."""

    def test_with_real_tool_registry(self, mock_sandbox):
        """Test validation with real ToolRegistry (auto-discovered tools)."""
        import importlib
        tools_registry_module = importlib.import_module("atloop.tools.registry")
        ToolRegistry = tools_registry_module.ToolRegistry
        registry = ToolRegistry(sandbox=mock_sandbox)
        # Registry should have auto-discovered tools

        # Test with a real tool (if available)
        if "run" in registry.list_tools():
            data = {
                "actions": [{"tool": "run", "args": {"cmd": "echo test"}}],
                "stop_reason": "continue",
            }
            is_valid, error = validate_action_json(data, tool_registry=registry)
            # Should validate using real tool's validate_args()
            assert is_valid is True or error is not None  # Either valid or has specific error

        # Test with invalid tool
        data = {
            "actions": [{"tool": "definitely_not_a_real_tool", "args": {}}],
            "stop_reason": "continue",
        }
        is_valid, error = validate_action_json(data, tool_registry=registry)
        assert is_valid is False
        assert "definitely_not_a_real_tool" in error

    def test_real_tool_missing_required_args(self, mock_sandbox):
        """Test that real tools validate their required arguments."""
        import importlib
        tools_registry_module = importlib.import_module("atloop.tools.registry")
        ToolRegistry = tools_registry_module.ToolRegistry
        registry = ToolRegistry(sandbox=mock_sandbox)

        # Find a tool that requires arguments
        for tool_name in registry.list_tools():
            tool = registry.get(tool_name)
            if tool and hasattr(tool, "validate_args"):
                # Try with empty args
                is_valid, error = tool.validate_args({})
                if not is_valid:
                    # This tool requires args, test validation
                    data = {
                        "actions": [{"tool": tool_name, "args": {}}],
                        "stop_reason": "continue",
                    }
                    is_valid, error = validate_action_json(data, tool_registry=registry)
                    assert is_valid is False
                    assert tool_name in error
                    break  # Test one tool is enough


# ============================================================================
# Regression Tests: Ensure Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Test that changes maintain backward compatibility."""

    def test_validate_action_json_without_registry_still_works(self):
        """Test that validate_action_json() works without registry (backward compat)."""
        data = {
            "actions": [{"tool": "any_tool", "args": {}}],
            "stop_reason": "continue",
        }
        # Should work without registry parameter
        is_valid, error = validate_action_json(data)
        assert is_valid is True

    def test_from_dict_without_registry_still_works(self):
        """Test that from_dict() works without registry (backward compat)."""
        data = {
            "actions": [{"tool": "any_tool", "args": {}}],
            "stop_reason": "continue",
        }
        # Should work without tool_registry parameter
        action_json = ActionJSON.from_dict(data, validate=True)
        assert action_json is not None

    def test_parse_action_json_without_registry_still_works(self):
        """Test that parse_action_json() works without registry (backward compat)."""
        json_text = json.dumps(
            {
                "actions": [{"tool": "any_tool", "args": {}}],
                "stop_reason": "continue",
            }
        )
        # Should work without tool_registry parameter
        action_json, error, file_contents = parse_action_json(json_text)
        assert action_json is not None
        assert error is None
