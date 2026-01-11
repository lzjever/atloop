"""Integration tests for placeholder system with new format.

Tests cover:
1. Full workflow: PlanPhase -> ActPhase with placeholder handling
2. Memory recording with placeholder names
3. Placeholder info tracking across phases
4. Error handling and validation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from atloop.llm import ActionJSON
from atloop.memory.state import Memory
from atloop.orchestrator.phases.placeholder_info import PlaceholderInfoTracker
from atloop.orchestrator.phases.placeholder_replacer import PlaceholderReplacer


class TestPlaceholderInfoTracking:
    """Test placeholder info tracking functionality."""

    def test_extract_info_preserves_args_when_no_placeholder(self):
        """Test that args are preserved when no placeholder is used."""
        actions = [
            {"tool": "read_file", "args": {"path": "test.py"}},
            {"tool": "write_file", "args": {"path": "test.py", "content": "actual content"}},
        ]

        info_list = PlaceholderInfoTracker.extract_placeholder_info(actions)

        assert len(info_list) == 2
        assert info_list[0].tool == "read_file"
        assert info_list[0].placeholder is None
        assert info_list[0].args == {"path": "test.py"}

        assert info_list[1].tool == "write_file"
        assert info_list[1].placeholder is None
        assert info_list[1].args == {"path": "test.py", "content": "actual content"}

    def test_extract_info_sets_args_none_when_placeholder_exists(self):
        """Test that args are set to None when placeholder is used."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}},
        ]

        info_list = PlaceholderInfoTracker.extract_placeholder_info(actions)

        assert len(info_list) == 1
        assert info_list[0].tool == "write_file"
        assert info_list[0].placeholder == "WRITE_FILE_CONTENT_file:test.py"
        assert info_list[0].args is None  # Should be None when placeholder exists

    def test_extract_info_handles_all_tool_types(self):
        """Test extraction for all tool types that use placeholders."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:a.py"}},
            {"tool": "edit_file", "args": {"path": "b.py", "content": "EDIT_FILE_CONTENT_file:b.py"}},
            {"tool": "append_file", "args": {"path": "c.py", "content": "APPEND_FILE_CONTENT_file:c.py"}},
            {"tool": "run", "args": {"cmd": "SHELL_COMMAND_cmd:ls-la"}},
            {"tool": "run_python_script_string", "args": {"script": "PYTHON_SCRIPT_script:process"}},
            {"tool": "run_shell_script_string", "args": {"script": "SHELL_SCRIPT_script:cleanup"}},
        ]

        info_list = PlaceholderInfoTracker.extract_placeholder_info(actions)

        assert len(info_list) == 6
        assert all(info.placeholder is not None for info in info_list)
        assert all(info.args is None for info in info_list)  # All use placeholders

    def test_validate_run_tool_multiple_actions(self):
        """Test run tool validation with multiple actions."""
        actions = [
            {"tool": "read_file", "args": {"path": "test.py"}},
            {"tool": "run", "args": {"cmd": "SHELL_COMMAND_cmd:ls-la"}},  # Valid
            {"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}},
            {"tool": "run", "args": {"cmd": "ls -la"}},  # Invalid - direct command
        ]

        is_valid, error_msg, action_index = PlaceholderInfoTracker.validate_run_tool_placeholders(actions)

        assert is_valid is False
        assert error_msg is not None
        assert "action 4" in error_msg or "action 3" in error_msg  # Should point to the invalid one
        assert action_index == 4

    def test_validate_run_tool_all_valid(self):
        """Test run tool validation when all use placeholders."""
        actions = [
            {"tool": "run", "args": {"cmd": "SHELL_COMMAND_cmd:ls-la"}},
            {"tool": "run", "args": {"cmd": "SHELL_COMMAND_cmd:cat-file"}},
        ]

        is_valid, error_msg, action_index = PlaceholderInfoTracker.validate_run_tool_placeholders(actions)

        assert is_valid is True
        assert error_msg is None
        assert action_index is None


class TestPlaceholderReplacementIntegration:
    """Test placeholder replacement with new format names."""

    def test_replace_with_complex_names(self):
        """Test replacement with complex placeholder names."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file: test.py (backup #1)"},
            },
            {
                "tool": "run",
                "args": {"cmd": "SHELL_COMMAND_cmd: python3 test.py --verbose"},
            },
        ]
        file_contents = {
            "WRITE_FILE_CONTENT_file: test.py (backup #1)": "def hello():\n    pass",
            "SHELL_COMMAND_cmd: python3 test.py --verbose": "python3 test.py --verbose",
        }

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 2
        assert len(missing) == 0
        assert replaced[0]["args"]["content"] == "def hello():\n    pass"
        assert replaced[1]["args"]["cmd"] == "python3 test.py --verbose"

    def test_replace_preserves_other_args(self):
        """Test that replacement preserves other arguments."""
        actions = [
            {
                "tool": "write_file",
                "args": {
                    "path": "test.py",
                    "content": "WRITE_FILE_CONTENT_file:test.py",
                    "mode": "w",
                    "encoding": "utf-8",
                },
            },
        ]
        file_contents = {"WRITE_FILE_CONTENT_file:test.py": "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "content"
        assert replaced[0]["args"]["path"] == "test.py"
        assert replaced[0]["args"]["mode"] == "w"
        assert replaced[0]["args"]["encoding"] == "utf-8"

    def test_replace_with_unicode_in_placeholder_name(self):
        """Test replacement with unicode characters in placeholder name."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_文件:测试.py"}},
        ]
        file_contents = {"WRITE_FILE_CONTENT_文件:测试.py": "def hello():\n    pass"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "def hello():\n    pass"
        assert len(missing) == 0

    def test_replace_with_very_long_placeholder_name(self):
        """Test replacement with very long placeholder name."""
        long_name = "WRITE_FILE_CONTENT_" + "a" * 500
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": long_name}},
        ]
        file_contents = {long_name: "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "content"
        assert len(missing) == 0


class TestPlaceholderMemoryRecording:
    """Test memory recording with placeholder information."""

    def test_memory_record_format_with_placeholder(self):
        """Test the format of tool_results_history record with placeholder."""
        # Simulate what ActPhase would create
        tool_result_record = {
            "step": 1,
            "tool": "write_file",
            "args": None,  # None when placeholder was used
            "placeholder": "WRITE_FILE_CONTENT_file:test.py",
            "result": {"ok": True, "stdout": "File created"},
        }

        # Verify structure
        assert tool_result_record["step"] == 1
        assert tool_result_record["tool"] == "write_file"
        assert tool_result_record["placeholder"] == "WRITE_FILE_CONTENT_file:test.py"
        assert tool_result_record["args"] is None

    def test_memory_record_format_without_placeholder(self):
        """Test the format of tool_results_history record without placeholder."""
        # Simulate what ActPhase would create for tool without placeholder
        tool_result_record = {
            "step": 1,
            "tool": "read_file",
            "args": {"path": "test.py"},  # Actual args when no placeholder
            "placeholder": None,
            "result": {"ok": True, "stdout": "file content"},
        }

        # Verify structure
        assert tool_result_record["step"] == 1
        assert tool_result_record["tool"] == "read_file"
        assert tool_result_record["placeholder"] is None
        assert tool_result_record["args"] == {"path": "test.py"}

    def test_memory_record_mixed_placeholders_and_args(self):
        """Test memory records with mix of placeholders and direct args."""
        records = [
            {
                "step": 1,
                "tool": "write_file",
                "args": None,
                "placeholder": "WRITE_FILE_CONTENT_file:test.py",
                "result": {"ok": True},
            },
            {
                "step": 1,
                "tool": "read_file",
                "args": {"path": "test.py"},
                "placeholder": None,
                "result": {"ok": True},
            },
        ]

        # Verify structure
        assert records[0]["placeholder"] is not None
        assert records[0]["args"] is None
        assert records[1]["placeholder"] is None
        assert records[1]["args"] is not None


class TestPlaceholderEdgeCasesIntegration:
    """Test edge cases in placeholder system integration."""

    def test_placeholder_name_with_escaped_characters(self):
        """Test placeholder name with characters that might need escaping."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py\nwith\nnewlines"}},
        ]
        file_contents = {"WRITE_FILE_CONTENT_file:test.py\nwith\nnewlines": "content"}

        # This should work - placeholder name can contain newlines
        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "content"
        assert len(missing) == 0

    def test_placeholder_name_matching_content_pattern(self):
        """Test placeholder name that looks like it could be content."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_actual python code here"}},
        ]
        file_contents = {"WRITE_FILE_CONTENT_actual python code here": "def hello():\n    pass"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "def hello():\n    pass"
        assert len(missing) == 0

    def test_empty_placeholder_name_handling(self):
        """Test handling of placeholder with empty name (should be invalid)."""
        # Empty name after prefix should be invalid
        assert PlaceholderReplacer._is_valid_placeholder("WRITE_FILE_CONTENT_") is False

    def test_placeholder_name_with_only_whitespace(self):
        """Test placeholder name with only whitespace."""
        # Whitespace-only name should be valid (per spec: any string)
        assert PlaceholderReplacer._is_valid_placeholder("WRITE_FILE_CONTENT_   ") is True

    def test_multiple_placeholders_same_type_different_names(self):
        """Test multiple placeholders of same type with different descriptive names."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:a.py"}},
            {"tool": "write_file", "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:b.py"}},
            {"tool": "write_file", "args": {"path": "c.py", "content": "WRITE_FILE_CONTENT_file:c.py"}},
        ]
        file_contents = {
            "WRITE_FILE_CONTENT_file:a.py": "content_a",
            "WRITE_FILE_CONTENT_file:b.py": "content_b",
            "WRITE_FILE_CONTENT_file:c.py": "content_c",
        }

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 3
        assert len(missing) == 0
        assert replaced[0]["args"]["content"] == "content_a"
        assert replaced[1]["args"]["content"] == "content_b"
        assert replaced[2]["args"]["content"] == "content_c"

    def test_placeholder_extraction_with_json_in_content(self):
        """Test extracting placeholder when content contains JSON-like text."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "config.json", "content": "WRITE_FILE_CONTENT_file:config.json"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:config.json))---
{
  "key": "value",
  "nested": {
    "item": 123
  }
}
"""
        from atloop.llm.schema import _extract_file_contents

        contents = _extract_file_contents(text)

        assert len(contents) == 1
        content = contents["WRITE_FILE_CONTENT_file:config.json"]
        assert '"key": "value"' in content
        assert '"nested":' in content

    def test_placeholder_removal_preserves_complex_json(self):
        """Test that placeholder removal preserves complex JSON structure."""
        text = """{
  "current_step_thoughts": "Creating config",
  "plan": ["Step 1", "Step 2"],
  "actions": [
    {
      "tool": "write_file",
      "args": {
        "path": "config.json",
        "content": "WRITE_FILE_CONTENT_file:config.json"
      }
    }
  ],
  "stop_reason": "continue",
  "result_message": "Done"
}

---((WRITE_FILE_CONTENT_file:config.json))---
{"key": "value"}
"""
        from atloop.llm.schema import _remove_file_content_sections

        result = _remove_file_content_sections(text)

        # Should be valid JSON
        import json
        parsed = json.loads(result)
        assert "actions" in parsed
        assert "stop_reason" in parsed
        assert "current_step_thoughts" in parsed
        assert len(parsed["actions"]) == 1
