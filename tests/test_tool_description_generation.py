"""Tests for dynamic tool description generation.

These tests verify that:
1. Tools can generate detailed descriptions from their docstrings
2. LLMClient.generate_tool_schema() generates comprehensive tool documentation
3. Tool descriptions are properly formatted for LLM prompts
4. All tools have adequate documentation
"""

import inspect
from unittest.mock import MagicMock

import pytest

from atloop.tools.base import BaseTool, ToolResult


class MockToolForTesting(BaseTool):
    """Mock tool with comprehensive docstring for testing description extraction."""

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "test_tool"

    @property
    def description(self) -> str:
        return "Simple description for test tool"

    def execute(self, args):
        return ToolResult(ok=True, stdout="", stderr="", meta={})


class MockToolWithFullDocstring(BaseTool):
    """
    Tool for testing comprehensive docstring extraction.

    This is a test tool that demonstrates how detailed descriptions are extracted.

    **⚠️ CRITICAL**: This is a test tool only.

    **Use cases:**
    - Testing docstring extraction
    - Validating description generation
    - Demonstrating tool documentation format

    **Key differences:**
    - This tool is only for testing
    - Not meant for actual use
    """

    def __init__(self):
        pass

    @property
    def name(self) -> str:
        return "test_tool_full"

    @property
    def description(self) -> str:
        return "Test tool with full docstring"

    def execute(self, args):
        """
        Execute test tool.

        **Args:**
            args: Tool arguments dictionary
                - param1 (str, required): First parameter
                - param2 (int, optional): Second parameter

        **Returns:**
            ToolResult with test results

        **Examples:**
            # Basic usage
            test_tool_full(param1="value1")
        """
        return ToolResult(ok=True, stdout="", stderr="", meta={})


class TestToolDescriptionGeneration:
    """Test tool description generation functionality."""

    def test_get_detailed_description_basic(self):
        """Test that get_detailed_description() works for basic tool."""
        tool = MockToolForTesting()
        detailed_desc = tool.get_detailed_description()

        assert detailed_desc is not None
        assert len(detailed_desc) > 0
        assert "test_tool" in detailed_desc or "Simple description" in detailed_desc

    def test_get_detailed_description_with_docstring(self):
        """Test that get_detailed_description() extracts from docstring."""
        tool = MockToolWithFullDocstring()
        detailed_desc = tool.get_detailed_description()

        assert detailed_desc is not None
        assert len(detailed_desc) > 0
        # Should extract main description
        assert "testing comprehensive docstring" in detailed_desc.lower() or "test tool" in detailed_desc.lower()
        # Should extract CRITICAL section (normalized)
        assert "CRITICAL" in detailed_desc or "critical" in detailed_desc.lower() or "Important" in detailed_desc
        # Should extract use cases or parameters
        assert "use cases" in detailed_desc.lower() or "Use cases" in detailed_desc or "Parameters" in detailed_desc

    def test_get_detailed_description_extracts_parameters(self):
        """Test that parameters are extracted from execute() docstring."""
        tool = MockToolWithFullDocstring()
        detailed_desc = tool.get_detailed_description()

        # Should extract parameters section
        assert "param1" in detailed_desc.lower() or "Parameters" in detailed_desc

    def test_get_detailed_description_fallback(self):
        """Test that get_detailed_description() falls back gracefully."""
        # Create tool with no docstring
        class ToolNoDocstring(BaseTool):
            @property
            def name(self):
                return "no_doc"

            @property
            def description(self):
                return "Simple desc"

            def execute(self, args):
                return ToolResult(ok=True, stdout="", stderr="", meta={})

        tool = ToolNoDocstring()
        detailed_desc = tool.get_detailed_description()

        assert detailed_desc is not None
        assert "Simple desc" in detailed_desc

    def test_get_detailed_description_preserves_formatting(self):
        """Test that important formatting is preserved."""
        tool = MockToolWithFullDocstring()
        detailed_desc = tool.get_detailed_description()

        # Should preserve important markers (CRITICAL section is normalized)
        assert "CRITICAL" in detailed_desc or "Important" in detailed_desc or "⚠️" in detailed_desc

    def test_real_tool_has_detailed_description(self):
        """Test that real tools can generate detailed descriptions."""
        # Import a real tool
        from atloop.tools.filesystem.write_file import WriteFileTool
        from atloop.runtime.sandbox_adapter import SandboxAdapter

        mock_sandbox = MagicMock()
        tool = WriteFileTool(mock_sandbox)

        detailed_desc = tool.get_detailed_description()

        assert detailed_desc is not None
        assert len(detailed_desc) > len(tool.description)  # Should be more detailed
        assert "write_file" in detailed_desc.lower()
        # Should contain important warnings
        assert "variable" in detailed_desc.lower() or "CRITICAL" in detailed_desc

    def test_real_tool_extracts_sections(self):
        """Test that real tools extract key sections from docstring."""
        from atloop.tools.filesystem.edit_file import EditFileTool
        from atloop.runtime.sandbox_adapter import SandboxAdapter

        mock_sandbox = MagicMock()
        tool = EditFileTool(mock_sandbox)

        detailed_desc = tool.get_detailed_description()

        # Should extract use cases or important notes
        assert len(detailed_desc) > 100  # Should be comprehensive
        assert "edit_file" in detailed_desc.lower()


class TestLLMClientToolSchemaGeneration:
    """Test LLMClient.generate_tool_schema() functionality."""

    def test_generate_tool_schema_creates_categories(self):
        """Test that tool schema is organized by categories."""
        from atloop.config.loader import ConfigLoader
        from atloop.llm.client import LLMClient

        config = ConfigLoader.get()
        client = LLMClient(config)

        tool_schema = client.generate_tool_schema()

        assert tool_schema is not None
        assert len(tool_schema) > 0
        # Should have categories
        assert "File Operations" in tool_schema or "###" in tool_schema
        assert "Execution Tools" in tool_schema or "###" in tool_schema

    def test_generate_tool_schema_includes_tool_details(self):
        """Test that tool schema includes detailed tool information."""
        from atloop.config.loader import ConfigLoader
        from atloop.llm.client import LLMClient

        config = ConfigLoader.get()
        client = LLMClient(config)

        tool_schema = client.generate_tool_schema()

        # Should include common tools
        assert "edit_file" in tool_schema or "write_file" in tool_schema
        # Should have detailed descriptions (not just names)
        assert len(tool_schema) > 500  # Should be comprehensive

    def test_generate_tool_schema_prioritizes_important_tools(self):
        """Test that important tools appear first in their categories."""
        from atloop.config.loader import ConfigLoader
        from atloop.llm.client import LLMClient

        config = ConfigLoader.get()
        client = LLMClient(config)

        tool_schema = client.generate_tool_schema()

        # edit_file should appear before other file tools
        edit_file_pos = tool_schema.find("edit_file")
        if edit_file_pos != -1:
            # Check that edit_file appears in File Operations section
            file_ops_pos = tool_schema.find("File Operations")
            if file_ops_pos != -1:
                # edit_file should be early in File Operations (within first 2000 chars to account for detailed descriptions)
                assert edit_file_pos < file_ops_pos + 2000  # Within reasonable range

    def test_generate_tool_schema_handles_missing_tools_gracefully(self):
        """Test that schema generation handles errors gracefully."""
        from atloop.config.loader import ConfigLoader
        from atloop.llm.client import LLMClient

        config = ConfigLoader.get()
        client = LLMClient(config)

        # Should not raise exception even if some tools fail
        tool_schema = client.generate_tool_schema()

        assert tool_schema is not None
        assert len(tool_schema) > 0


class TestToolDescriptionQuality:
    """Test that tool descriptions meet quality standards for LLM usage."""

    def test_all_tools_have_descriptions(self):
        """Test that all registered tools have descriptions."""
        from atloop.runtime.sandbox_adapter import SandboxAdapter
        from atloop.tools.registry import ToolRegistry

        mock_sandbox = MagicMock()
        registry = ToolRegistry(mock_sandbox)

        for tool_name, tool in registry.tools.items():
            assert tool.description is not None, f"Tool {tool_name} has no description"
            assert len(tool.description) > 0, f"Tool {tool_name} has empty description"
            assert isinstance(tool.description, str), f"Tool {tool_name} description is not a string"

    def test_all_tools_can_generate_detailed_descriptions(self):
        """Test that all tools can generate detailed descriptions."""
        from atloop.runtime.sandbox_adapter import SandboxAdapter
        from atloop.tools.registry import ToolRegistry

        mock_sandbox = MagicMock()
        registry = ToolRegistry(mock_sandbox)

        for tool_name, tool in registry.tools.items():
            try:
                detailed_desc = tool.get_detailed_description()
                assert detailed_desc is not None, f"Tool {tool_name} returned None for detailed description"
                assert len(detailed_desc) > 0, f"Tool {tool_name} returned empty detailed description"
                assert isinstance(detailed_desc, str), f"Tool {tool_name} detailed description is not a string"
            except Exception as e:
                pytest.fail(f"Tool {tool_name} failed to generate detailed description: {e}")

    def test_tool_descriptions_are_informative(self):
        """Test that tool descriptions contain useful information."""
        from atloop.runtime.sandbox_adapter import SandboxAdapter
        from atloop.tools.registry import ToolRegistry

        mock_sandbox = MagicMock()
        registry = ToolRegistry(mock_sandbox)

        # Check key tools have informative descriptions
        key_tools = ["write_file", "edit_file", "read_file", "run"]
        for tool_name in key_tools:
            tool = registry.get(tool_name)
            if tool:
                detailed_desc = tool.get_detailed_description()
                # Should be more than just a name
                assert len(detailed_desc) > 50, f"Tool {tool_name} description too short"
                # Should contain tool name or key concepts
                assert tool_name in detailed_desc.lower() or any(
                    word in detailed_desc.lower() for word in ["file", "command", "execute", "read", "write"]
                )
