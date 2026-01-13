"""Comprehensive tests for new placeholder format with double brackets.

Tests cover:
1. New double bracket format: ---((TYPE_name))---
2. Placeholder names with any characters (not just alphanumeric)
3. Uniqueness validation within same round
4. Extraction and parsing
5. Replacement logic
6. Integration with PlanPhase and ActPhase
7. Memory recording

These tests are written based on interface specification, not implementation details.
They challenge the implementation to ensure correctness.
"""

from atloop.llm.schema import (
    _extract_file_contents,
    _remove_file_content_sections,
    parse_action_json,
)
from atloop.orchestrator.phases.placeholder_info import (
    PlaceholderInfoTracker,
)
from atloop.orchestrator.phases.placeholder_replacer import (
    PlaceholderReplacer,
)


class TestPlaceholderExtractionDoubleBrackets:
    """Test placeholder extraction with new double bracket format."""

    def test_extract_single_placeholder_double_brackets(self):
        """Test extracting single placeholder with double brackets."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
def hello():
    print("Hello, world!")
    return True
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 1, f"Expected 1 placeholder, got {len(contents)}"
        assert "WRITE_FILE_CONTENT_file:test.py" in contents
        assert "def hello():" in contents["WRITE_FILE_CONTENT_file:test.py"]
        assert 'print("Hello, world!")' in contents["WRITE_FILE_CONTENT_file:test.py"]

    def test_extract_multiple_placeholders_double_brackets(self):
        """Test extracting multiple placeholders with double brackets."""
        text = """{
  "actions": [
    {"tool": "write_file", "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:a.py"}},
    {"tool": "write_file", "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:b.py"}}
  ],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:a.py))---
def func_a():
    return "a"
---((WRITE_FILE_CONTENT_file:b.py))---
def func_b():
    return "b"
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 2
        assert "WRITE_FILE_CONTENT_file:a.py" in contents
        assert "WRITE_FILE_CONTENT_file:b.py" in contents
        assert "func_a" in contents["WRITE_FILE_CONTENT_file:a.py"]
        assert "func_b" in contents["WRITE_FILE_CONTENT_file:b.py"]

    def test_extract_placeholder_with_special_characters_in_name(self):
        """Test placeholder names with special characters (spaces, colons, etc.)."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file: test.py with spaces"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file: test.py with spaces))---
def hello():
    pass
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 1
        assert "WRITE_FILE_CONTENT_file: test.py with spaces" in contents
        assert "def hello():" in contents["WRITE_FILE_CONTENT_file: test.py with spaces"]

    def test_extract_placeholder_with_unicode_in_name(self):
        """Test placeholder names with unicode characters."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_文件:测试.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_文件:测试.py))---
def hello():
    pass
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 1
        assert "WRITE_FILE_CONTENT_文件:测试.py" in contents

    def test_extract_placeholder_with_special_chars_in_content(self):
        """Test placeholder content with special characters (brackets, quotes, etc.)."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
def func():
    # Content with (brackets) and "quotes"
    if x > 0:
        return "value"
    return None
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 1
        content = contents["WRITE_FILE_CONTENT_file:test.py"]
        assert "(brackets)" in content
        assert '"quotes"' in content
        assert "if x > 0:" in content

    def test_extract_placeholder_name_with_brackets(self):
        """Test placeholder name containing brackets (edge case)."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:(test).py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:(test).py))---
def hello():
    pass
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 1
        assert "WRITE_FILE_CONTENT_file:(test).py" in contents

    def test_extract_all_placeholder_types(self):
        """Test extracting all placeholder types with double brackets."""
        text = """{
  "actions": [
    {"tool": "write_file", "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:a.py"}},
    {"tool": "edit_file", "args": {"path": "b.py", "content": "EDIT_FILE_CONTENT_file:b.py"}},
    {"tool": "append_file", "args": {"path": "c.py", "content": "APPEND_FILE_CONTENT_file:c.py"}},
    {"tool": "run", "args": {"cmd": "SHELL_COMMAND_cmd:ls-la"}},
    {"tool": "run_python_script_string", "args": {"script": "PYTHON_SCRIPT_script:process-data"}},
    {"tool": "run_shell_script_string", "args": {"script": "SHELL_SCRIPT_script:cleanup"}}
  ],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:a.py))---
content1
---((EDIT_FILE_CONTENT_file:b.py))---
<old>old</old><new>new</new>
---((APPEND_FILE_CONTENT_file:c.py))---
append
---((SHELL_COMMAND_cmd:ls-la))---
ls -la
---((PYTHON_SCRIPT_script:process-data))---
print("data")
---((SHELL_SCRIPT_script:cleanup))---
rm -rf /tmp/*
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 6
        assert "WRITE_FILE_CONTENT_file:a.py" in contents
        assert "EDIT_FILE_CONTENT_file:b.py" in contents
        assert "APPEND_FILE_CONTENT_file:c.py" in contents
        assert "SHELL_COMMAND_cmd:ls-la" in contents
        assert "PYTHON_SCRIPT_script:process-data" in contents
        assert "SHELL_SCRIPT_script:cleanup" in contents

    def test_extract_placeholder_with_empty_content(self):
        """Test placeholder with empty content."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---

"""
        contents = _extract_file_contents(text)

        assert len(contents) == 1
        assert "WRITE_FILE_CONTENT_file:test.py" in contents
        assert contents["WRITE_FILE_CONTENT_file:test.py"].strip() == ""

    def test_extract_placeholder_with_multiline_content(self):
        """Test placeholder with multiline content."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
line1
line2
line3
line4
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 1
        content = contents["WRITE_FILE_CONTENT_file:test.py"]
        assert "line1" in content
        assert "line2" in content
        assert "line3" in content
        assert "line4" in content
        assert content.count("\n") >= 3

    def test_extract_placeholder_does_not_match_single_brackets(self):
        """Test that single bracket format is NOT matched (backward compatibility removed)."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---(WRITE_FILE_CONTENT_file:test.py)---
def hello():
    pass
"""
        contents = _extract_file_contents(text)

        # Single bracket format should NOT be extracted
        assert len(contents) == 0

    def test_extract_placeholder_with_content_containing_double_brackets(self):
        """Test placeholder content that contains double brackets (should not interfere)."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
def func():
    # This is ((not a placeholder))
    if x > 0:
        return ((value))
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 1
        content = contents["WRITE_FILE_CONTENT_file:test.py"]
        assert "((not a placeholder))" in content
        assert "((value))" in content


class TestPlaceholderRemovalDoubleBrackets:
    """Test removing placeholder sections with double brackets."""

    def test_remove_single_placeholder_section(self):
        """Test removing single placeholder section."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
def hello():
    pass
"""
        result = _remove_file_content_sections(text)

        assert "---((WRITE_FILE_CONTENT_file:test.py))---" not in result
        assert "def hello():" not in result
        assert '"stop_reason": "continue"' in result
        assert '"tool": "write_file"' in result

    def test_remove_multiple_placeholder_sections(self):
        """Test removing multiple placeholder sections."""
        text = """{
  "actions": [
    {"tool": "write_file", "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:a.py"}},
    {"tool": "write_file", "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:b.py"}}
  ],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:a.py))---
content1
---((WRITE_FILE_CONTENT_file:b.py))---
content2
"""
        result = _remove_file_content_sections(text)

        assert "---((WRITE_FILE_CONTENT_file:a.py))---" not in result
        assert "---((WRITE_FILE_CONTENT_file:b.py))---" not in result
        assert "content1" not in result
        assert "content2" not in result
        assert '"tool": "write_file"' in result

    def test_remove_placeholder_preserves_json_structure(self):
        """Test that JSON structure is preserved after removal."""
        text = """{
  "current_step_thoughts": "Creating file",
  "plan": ["Step 1"],
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
def hello():
    pass
"""
        result = _remove_file_content_sections(text)

        # Should be valid JSON after removal
        import json

        parsed = json.loads(result)
        assert "actions" in parsed
        assert "stop_reason" in parsed
        assert len(parsed["actions"]) == 1


class TestPlaceholderValidationAnyString:
    """Test placeholder validation with any string names."""

    def test_validate_placeholder_with_simple_name(self):
        """Test validation of placeholder with simple name."""
        assert PlaceholderReplacer._is_valid_placeholder("WRITE_FILE_CONTENT_file:test.py") is True

    def test_validate_placeholder_with_spaces(self):
        """Test validation of placeholder with spaces in name."""
        assert PlaceholderReplacer._is_valid_placeholder("WRITE_FILE_CONTENT_file: test.py") is True

    def test_validate_placeholder_with_special_chars(self):
        """Test validation of placeholder with special characters."""
        assert (
            PlaceholderReplacer._is_valid_placeholder("WRITE_FILE_CONTENT_file:(test).py") is True
        )
        assert PlaceholderReplacer._is_valid_placeholder("SHELL_COMMAND_cmd:ls -la") is True
        assert (
            PlaceholderReplacer._is_valid_placeholder("EDIT_FILE_CONTENT_file:test.py#backup")
            is True
        )

    def test_validate_placeholder_with_unicode(self):
        """Test validation of placeholder with unicode characters."""
        assert PlaceholderReplacer._is_valid_placeholder("WRITE_FILE_CONTENT_文件:测试.py") is True

    def test_validate_placeholder_with_empty_name(self):
        """Test validation of placeholder with empty name (should be invalid)."""
        assert PlaceholderReplacer._is_valid_placeholder("WRITE_FILE_CONTENT_") is False

    def test_validate_placeholder_without_prefix(self):
        """Test validation of non-placeholder strings."""
        assert PlaceholderReplacer._is_valid_placeholder("not_a_placeholder") is False
        assert PlaceholderReplacer._is_valid_placeholder("actual content") is False
        assert PlaceholderReplacer._is_valid_placeholder("") is False

    def test_validate_all_placeholder_types(self):
        """Test validation of all placeholder types."""
        assert PlaceholderReplacer._is_valid_placeholder("WRITE_FILE_CONTENT_file:test.py") is True
        assert PlaceholderReplacer._is_valid_placeholder("EDIT_FILE_CONTENT_file:test.py") is True
        assert PlaceholderReplacer._is_valid_placeholder("APPEND_FILE_CONTENT_file:test.py") is True
        assert PlaceholderReplacer._is_valid_placeholder("SHELL_COMMAND_cmd:ls-la") is True
        assert PlaceholderReplacer._is_valid_placeholder("PYTHON_SCRIPT_script:process") is True
        assert PlaceholderReplacer._is_valid_placeholder("SHELL_SCRIPT_script:cleanup") is True

    def test_detect_placeholder_type(self):
        """Test placeholder type detection."""
        assert (
            PlaceholderReplacer._detect_placeholder_type("WRITE_FILE_CONTENT_file:test.py")
            == "WRITE_FILE_CONTENT"
        )
        assert (
            PlaceholderReplacer._detect_placeholder_type("EDIT_FILE_CONTENT_file:test.py")
            == "EDIT_FILE_CONTENT"
        )
        assert (
            PlaceholderReplacer._detect_placeholder_type("SHELL_COMMAND_cmd:ls-la")
            == "SHELL_COMMAND"
        )
        assert PlaceholderReplacer._detect_placeholder_type("not_a_placeholder") is None


class TestPlaceholderReplacementNewFormat:
    """Test placeholder replacement with new format."""

    def test_replace_write_file_with_new_format(self):
        """Test replacing write_file placeholder with new format name."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            }
        ]
        file_contents = {"WRITE_FILE_CONTENT_file:test.py": "def hello():\n    pass"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "def hello():\n    pass"
        assert len(missing) == 0

    def test_replace_with_special_characters_in_name(self):
        """Test replacement with special characters in placeholder name."""
        actions = [
            {
                "tool": "write_file",
                "args": {
                    "path": "test.py",
                    "content": "WRITE_FILE_CONTENT_file: test.py with spaces",
                },
            }
        ]
        file_contents = {"WRITE_FILE_CONTENT_file: test.py with spaces": "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "content"
        assert len(missing) == 0

    def test_replace_run_command_placeholder(self):
        """Test replacing run command placeholder (required)."""
        actions = [
            {"tool": "run", "args": {"cmd": "SHELL_COMMAND_cmd:ls-la"}},
        ]
        file_contents = {"SHELL_COMMAND_cmd:ls-la": "ls -la"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["cmd"] == "ls -la"
        assert len(missing) == 0

    def test_replace_multiple_different_names(self):
        """Test replacing multiple placeholders with different descriptive names."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:a.py"},
            },
            {
                "tool": "write_file",
                "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:b.py"},
            },
            {
                "tool": "edit_file",
                "args": {"path": "c.py", "content": "EDIT_FILE_CONTENT_file:c.py"},
            },
        ]
        file_contents = {
            "WRITE_FILE_CONTENT_file:a.py": "content_a",
            "WRITE_FILE_CONTENT_file:b.py": "content_b",
            "EDIT_FILE_CONTENT_file:c.py": "<old>old</old><new>new</new>",
        }

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 3
        assert replaced[0]["args"]["content"] == "content_a"
        assert replaced[1]["args"]["content"] == "content_b"
        assert replaced[2]["args"]["content"] == "<old>old</old><new>new</new>"
        assert len(missing) == 0


class TestPlaceholderUniqueness:
    """Test placeholder name uniqueness validation."""

    def test_duplicate_placeholder_names_detected(self):
        """Test that duplicate placeholder names are detected."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },
            {
                "tool": "write_file",
                "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },  # Duplicate!
        ]

        # This should be caught by PlanPhase validation
        # We test the extraction logic here
        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)

        assert len(placeholder_info) == 2
        assert placeholder_info[0].placeholder == "WRITE_FILE_CONTENT_file:test.py"
        assert placeholder_info[1].placeholder == "WRITE_FILE_CONTENT_file:test.py"  # Duplicate

    def test_unique_placeholder_names_allowed(self):
        """Test that unique placeholder names are allowed."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:a.py"},
            },
            {
                "tool": "write_file",
                "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:b.py"},
            },
        ]

        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)

        assert len(placeholder_info) == 2
        assert placeholder_info[0].placeholder == "WRITE_FILE_CONTENT_file:a.py"
        assert placeholder_info[1].placeholder == "WRITE_FILE_CONTENT_file:b.py"
        assert placeholder_info[0].placeholder != placeholder_info[1].placeholder

    def test_mixed_placeholder_types_unique(self):
        """Test that different placeholder types can have same descriptive name."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },
            {
                "tool": "edit_file",
                "args": {"path": "test.py", "content": "EDIT_FILE_CONTENT_file:test.py"},
            },
        ]

        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)

        assert len(placeholder_info) == 2
        # Different types, same descriptive name - should be allowed
        assert placeholder_info[0].placeholder == "WRITE_FILE_CONTENT_file:test.py"
        assert placeholder_info[1].placeholder == "EDIT_FILE_CONTENT_file:test.py"
        # Full names are different, so should be unique
        assert placeholder_info[0].placeholder != placeholder_info[1].placeholder


class TestPlaceholderInfoTracker:
    """Test PlaceholderInfoTracker functionality."""

    def test_extract_placeholder_info_write_file(self):
        """Test extracting placeholder info from write_file action."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },
        ]

        info_list = PlaceholderInfoTracker.extract_placeholder_info(actions)

        assert len(info_list) == 1
        assert info_list[0].tool == "write_file"
        assert info_list[0].placeholder == "WRITE_FILE_CONTENT_file:test.py"
        assert info_list[0].args is None  # Should be None when placeholder exists

    def test_extract_placeholder_info_without_placeholder(self):
        """Test extracting info when no placeholder is used."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "actual content"}},
        ]

        info_list = PlaceholderInfoTracker.extract_placeholder_info(actions)

        assert len(info_list) == 1
        assert info_list[0].tool == "write_file"
        assert info_list[0].placeholder is None
        assert info_list[0].args == {"path": "test.py", "content": "actual content"}

    def test_extract_placeholder_info_run_command(self):
        """Test extracting placeholder info from run command."""
        actions = [
            {"tool": "run", "args": {"cmd": "SHELL_COMMAND_cmd:ls-la"}},
        ]

        info_list = PlaceholderInfoTracker.extract_placeholder_info(actions)

        assert len(info_list) == 1
        assert info_list[0].tool == "run"
        assert info_list[0].placeholder == "SHELL_COMMAND_cmd:ls-la"
        assert info_list[0].args is None

    def test_extract_placeholder_info_non_content_tool(self):
        """Test extracting info from tool that doesn't use placeholders."""
        actions = [
            {"tool": "read_file", "args": {"path": "test.py"}},
        ]

        info_list = PlaceholderInfoTracker.extract_placeholder_info(actions)

        assert len(info_list) == 1
        assert info_list[0].tool == "read_file"
        assert info_list[0].placeholder is None
        assert info_list[0].args == {"path": "test.py"}

    def test_validate_run_tool_placeholders_required(self):
        """Test that run tool must use placeholder."""
        actions = [
            {"tool": "run", "args": {"cmd": "ls -la"}},  # Direct command - should fail
        ]

        is_valid, error_msg, action_index = PlaceholderInfoTracker.validate_run_tool_placeholders(
            actions
        )

        assert is_valid is False
        assert error_msg is not None
        assert "must use SHELL_COMMAND" in error_msg
        assert action_index == 1

    def test_validate_run_tool_placeholders_with_placeholder(self):
        """Test that run tool with placeholder is valid."""
        actions = [
            {"tool": "run", "args": {"cmd": "SHELL_COMMAND_cmd:ls-la"}},
        ]

        is_valid, error_msg, action_index = PlaceholderInfoTracker.validate_run_tool_placeholders(
            actions
        )

        assert is_valid is True
        assert error_msg is None
        assert action_index is None

    def test_validate_run_tool_empty_command(self):
        """Test validation with empty command (edge case)."""
        actions = [
            {"tool": "run", "args": {"cmd": ""}},
        ]

        is_valid, error_msg, action_index = PlaceholderInfoTracker.validate_run_tool_placeholders(
            actions
        )

        # Empty command should be valid (not a placeholder, but also not a direct command)
        assert is_valid is True


class TestParseActionJSONNewFormat:
    """Test parsing ActionJSON with new placeholder format."""

    def test_parse_with_double_bracket_placeholders(self):
        """Test parsing JSON with double bracket placeholders."""
        text = """{
  "current_step_thoughts": "Creating file",
  "plan": ["Step 1"],
  "actions": [
    {
      "tool": "write_file",
      "args": {
        "path": "test.py",
        "content": "WRITE_FILE_CONTENT_file:test.py"
      }
    }
  ],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
def hello():
    print("Hello, world!")
    return True
"""
        action_json, error, file_contents = parse_action_json(text)

        assert action_json is not None, f"Failed to parse: {error}"
        assert len(action_json.actions) == 1
        assert action_json.actions[0]["tool"] == "write_file"
        assert action_json.actions[0]["args"]["content"] == "WRITE_FILE_CONTENT_file:test.py"
        assert len(file_contents) == 1
        assert "WRITE_FILE_CONTENT_file:test.py" in file_contents
        assert "def hello():" in file_contents["WRITE_FILE_CONTENT_file:test.py"]

    def test_parse_with_multiple_placeholders_different_names(self):
        """Test parsing with multiple placeholders having unique descriptive names."""
        # Note: ActionJSON validation may limit multiple write_file actions
        # This test focuses on placeholder extraction, not action validation
        text = """{
  "actions": [
    {"tool": "write_file", "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:a.py"}},
    {"tool": "edit_file", "args": {"path": "b.py", "content": "EDIT_FILE_CONTENT_file:b.py"}},
    {"tool": "run", "args": {"cmd": "SHELL_COMMAND_cmd:python3-a.py"}}
  ],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:a.py))---
def func_a():
    return "a"
---((EDIT_FILE_CONTENT_file:b.py))---
<old>old</old><new>new</new>
---((SHELL_COMMAND_cmd:python3-a.py))---
python3 a.py
"""
        action_json, error, file_contents = parse_action_json(text)

        # Focus on file_contents extraction (action validation is separate concern)
        assert len(file_contents) == 3, (
            f"Expected 3 placeholders, got {len(file_contents)}: {list(file_contents.keys())}"
        )
        assert "WRITE_FILE_CONTENT_file:a.py" in file_contents
        assert "EDIT_FILE_CONTENT_file:b.py" in file_contents
        assert "SHELL_COMMAND_cmd:python3-a.py" in file_contents

    def test_parse_with_placeholder_name_containing_special_chars(self):
        """Test parsing with placeholder name containing special characters."""
        text = """{
  "actions": [
    {"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file: test.py (backup)"}}
  ],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file: test.py (backup)))---
def hello():
    pass
"""
        action_json, error, file_contents = parse_action_json(text)

        assert action_json is not None, f"Failed to parse: {error}"
        assert len(file_contents) == 1
        placeholder_name = "WRITE_FILE_CONTENT_file: test.py (backup)"
        assert placeholder_name in file_contents


class TestPlaceholderEdgeCases:
    """Test edge cases and boundary conditions with new format."""

    def test_placeholder_name_with_only_underscore(self):
        """Test placeholder name with only underscore."""
        assert (
            PlaceholderReplacer._is_valid_placeholder("WRITE_FILE_CONTENT_") is False
        )  # Empty name

    def test_placeholder_name_with_only_space(self):
        """Test placeholder name with only space."""
        assert (
            PlaceholderReplacer._is_valid_placeholder("WRITE_FILE_CONTENT_ ") is True
        )  # Space is valid

    def test_placeholder_name_very_long(self):
        """Test placeholder name that is very long."""
        long_name = "WRITE_FILE_CONTENT_" + "a" * 1000
        assert PlaceholderReplacer._is_valid_placeholder(long_name) is True

    def test_placeholder_name_with_newlines(self):
        """Test placeholder name with newlines (edge case)."""
        # This is technically valid per our spec (any string)
        name_with_newline = "WRITE_FILE_CONTENT_file:\ntest.py"
        assert PlaceholderReplacer._is_valid_placeholder(name_with_newline) is True

    def test_extract_placeholder_adjacent_to_another(self):
        """Test extracting placeholders that are adjacent (no content between)."""
        text = """---((WRITE_FILE_CONTENT_file:a.py))---
---((WRITE_FILE_CONTENT_file:b.py))---
content
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 2
        # First placeholder should have empty or minimal content
        # Second placeholder should have "content"
        assert "WRITE_FILE_CONTENT_file:a.py" in contents
        assert "WRITE_FILE_CONTENT_file:b.py" in contents

    def test_placeholder_content_with_delimiter_like_text(self):
        """Test placeholder content that looks like delimiter but isn't."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
# This is not a delimiter: ---((something))---
def func():
    # Another fake: ---((WRITE_FILE_CONTENT_file:fake.py))---
    pass
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 1
        content = contents["WRITE_FILE_CONTENT_file:test.py"]
        assert "---((something))---" in content
        assert "---((WRITE_FILE_CONTENT_file:fake.py))---" in content
