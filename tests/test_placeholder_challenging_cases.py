"""Challenging test cases that push the placeholder system to its limits.

These tests are designed to challenge the implementation and find edge cases
that might not be obvious. They test boundary conditions and error scenarios.
"""

import pytest

from atloop.llm.schema import _extract_file_contents, _remove_file_content_sections, parse_action_json
from atloop.orchestrator.phases.placeholder_info import PlaceholderInfoTracker
from atloop.orchestrator.phases.placeholder_replacer import (
    PlaceholderReplacer,
    PlaceholderReplacementError,
)


class TestPlaceholderChallengingCases:
    """Challenging test cases that push the system."""

    def test_placeholder_name_cannot_contain_delimiter_end_sequence(self):
        """Test that placeholder name cannot contain '))---' sequence (design limitation)."""
        # Design limitation: name cannot contain '))---' because it conflicts with delimiter end
        # But name CAN contain '))' as long as it's not followed by '---'
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_name:test))"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_name:test))))---
def hello():
    pass
"""
        contents = _extract_file_contents(text)

        # Should extract correctly - name contains '))' but not '))---'
        assert len(contents) == 1
        assert "WRITE_FILE_CONTENT_name:test))" in contents

    def test_placeholder_name_with_all_special_characters(self):
        """Test placeholder name with every possible special character."""
        special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        placeholder_name = f"WRITE_FILE_CONTENT_name:{special_chars}"
        
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": placeholder_name}},
        ]
        file_contents = {placeholder_name: "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "content"
        assert len(missing) == 0

    def test_placeholder_name_containing_newline_characters(self):
        """Test placeholder name containing newline (edge case)."""
        # Per spec, name can be any string, so newlines should be allowed
        name_with_newline = "WRITE_FILE_CONTENT_file:\ntest.py"
        
        # However, this might cause issues in JSON - test the validation
        assert PlaceholderReplacer._is_valid_placeholder(name_with_newline) is True

    def test_multiple_identical_placeholders_in_content(self):
        """Test content that contains multiple instances of placeholder-like text."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
# This file contains:
# ---((WRITE_FILE_CONTENT_file:fake1))---
# ---((WRITE_FILE_CONTENT_file:fake2))---
# But these are just comments, not real placeholders
def func():
    # Another fake: ---((SHELL_COMMAND_cmd:fake))---
    pass
"""
        contents = _extract_file_contents(text)

        # Should only extract the real placeholder, not the ones in content
        assert len(contents) == 1
        assert "WRITE_FILE_CONTENT_file:test.py" in contents
        content = contents["WRITE_FILE_CONTENT_file:test.py"]
        # Content should contain the fake delimiters
        assert "---((WRITE_FILE_CONTENT_file:fake1))---" in content
        assert "---((SHELL_COMMAND_cmd:fake))---" in content

    def test_placeholder_at_very_end_of_text_no_newline(self):
        """Test placeholder at end of text with no trailing newline."""
        text = """---((WRITE_FILE_CONTENT_file:test.py))---
content"""
        contents = _extract_file_contents(text)

        assert len(contents) == 1
        assert contents["WRITE_FILE_CONTENT_file:test.py"] == "content"

    def test_consecutive_placeholders_no_content_between(self):
        """Test consecutive placeholders with no content between them."""
        text = """---((WRITE_FILE_CONTENT_file:a.py))---
---((WRITE_FILE_CONTENT_file:b.py))---
content for b
"""
        contents = _extract_file_contents(text)

        assert len(contents) == 2
        # First should have empty or minimal content
        assert "WRITE_FILE_CONTENT_file:a.py" in contents
        # Second should have content
        assert contents["WRITE_FILE_CONTENT_file:b.py"] == "content for b\n"

    def test_placeholder_name_unicode_emojis(self):
        """Test placeholder name with unicode emojis."""
        emoji_name = "WRITE_FILE_CONTENT_file:test.py 🚀 📝"
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": emoji_name}},
        ]
        file_contents = {emoji_name: "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "content"
        assert len(missing) == 0

    def test_placeholder_name_with_control_characters(self):
        """Test placeholder name with control characters."""
        # Control characters like \t, \r, etc.
        name_with_control = "WRITE_FILE_CONTENT_file:\ttest.py"
        
        # Should be valid per spec (any string)
        assert PlaceholderReplacer._is_valid_placeholder(name_with_control) is True

    def test_extract_with_malformed_delimiter_missing_brackets(self):
        """Test that malformed delimiters are not matched."""
        text = """---(WRITE_FILE_CONTENT_file:test.py)---
content
---((WRITE_FILE_CONTENT_file:test2.py))---
content2
"""
        contents = _extract_file_contents(text)

        # Should only extract the correctly formatted one
        assert len(contents) == 1
        assert "WRITE_FILE_CONTENT_file:test2.py" in contents
        assert "WRITE_FILE_CONTENT_file:test.py" not in contents

    def test_extract_with_triple_brackets_should_not_match(self):
        """Test that triple brackets are not matched (only double)."""
        text = """---(((WRITE_FILE_CONTENT_file:test.py)))---
content
"""
        contents = _extract_file_contents(text)

        # Triple brackets should NOT match
        assert len(contents) == 0

    def test_placeholder_name_case_sensitivity(self):
        """Test that placeholder names are case-sensitive."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:Test.py"}},
        ]
        file_contents = {
            "WRITE_FILE_CONTENT_file:Test.py": "content1",
            "WRITE_FILE_CONTENT_file:test.py": "content2",  # Different case
        }

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        # Should match exact case
        assert replaced[0]["args"]["content"] == "content1"
        assert len(missing) == 0

    def test_duplicate_detection_case_sensitive(self):
        """Test that duplicate detection is case-sensitive."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:Test.py"}},
            {"tool": "write_file", "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:test.py"}},  # Different case
        ]

        # These should be considered unique (case-sensitive)
        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)
        placeholder_names = [info.placeholder for info in placeholder_info if info.placeholder]
        
        assert len(placeholder_names) == 2
        assert placeholder_names[0] != placeholder_names[1]  # Different due to case

    def test_placeholder_extraction_with_json_containing_delimiters(self):
        """Test extraction when JSON itself contains delimiter-like text."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "note": "This contains ---((something))--- in JSON",
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
def hello():
    pass
"""
        contents = _extract_file_contents(text)

        # Should extract correctly, JSON delimiter-like text should not interfere
        assert len(contents) == 1
        assert "WRITE_FILE_CONTENT_file:test.py" in contents

    def test_placeholder_removal_with_nested_json_in_content(self):
        """Test removal when content contains JSON structures."""
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
        result = _remove_file_content_sections(text)

        # Should preserve outer JSON structure
        import json
        parsed = json.loads(result)
        assert "actions" in parsed
        assert "stop_reason" in parsed
        # Should remove placeholder section
        assert "---((WRITE_FILE_CONTENT_file:config.json))---" not in result

    def test_run_command_validation_with_empty_string(self):
        """Test run command validation edge case - empty string."""
        actions = [
            {"tool": "run", "args": {"cmd": ""}},  # Empty - should be valid (not a direct command)
        ]

        is_valid, error_msg, action_index = PlaceholderInfoTracker.validate_run_tool_placeholders(actions)

        # Empty string is not a placeholder, but also not a direct command
        # Per current implementation, this should be valid
        assert is_valid is True

    def test_run_command_validation_with_whitespace_only(self):
        """Test run command validation with whitespace-only command."""
        actions = [
            {"tool": "run", "args": {"cmd": "   "}},  # Whitespace only
        ]

        is_valid, error_msg, action_index = PlaceholderInfoTracker.validate_run_tool_placeholders(actions)

        # Whitespace is not a placeholder, should fail validation
        assert is_valid is False

    def test_placeholder_name_matching_tool_name_pattern(self):
        """Test placeholder name that looks like it could be a tool name."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_write_file"}},
        ]
        file_contents = {"WRITE_FILE_CONTENT_write_file": "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "content"
        assert len(missing) == 0

    def test_extract_with_placeholder_containing_escaped_characters(self):
        """Test extraction with placeholder name containing escaped characters."""
        text = """---((WRITE_FILE_CONTENT_file:test\\n.py))---
content
"""
        contents = _extract_file_contents(text)

        # Should extract (backslash is just a character in the name)
        assert len(contents) == 1
        assert "WRITE_FILE_CONTENT_file:test\\n.py" in contents

    def test_placeholder_replacement_preserves_exact_whitespace(self):
        """Test that replacement preserves exact whitespace in content."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}},
        ]
        # Content with specific whitespace pattern
        content_with_whitespace = "line1\n\n  line2\n\tline3"
        file_contents = {"WRITE_FILE_CONTENT_file:test.py": content_with_whitespace}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == content_with_whitespace
        assert "\n\n" in replaced[0]["args"]["content"]  # Double newline preserved
        assert "\t" in replaced[0]["args"]["content"]  # Tab preserved

    def test_validate_uniqueness_with_very_similar_names(self):
        """Test uniqueness validation with very similar but different names."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:test.py"}},
            {"tool": "write_file", "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:test.py "}},  # Trailing space - different!
        ]

        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)
        placeholder_names = [info.placeholder for info in placeholder_info if info.placeholder]
        
        # These should be considered different (trailing space makes them unique)
        assert len(placeholder_names) == 2
        assert placeholder_names[0] != placeholder_names[1]

    def test_placeholder_extraction_performance_large_text(self):
        """Test extraction performance with very large text."""
        # Create large text with many placeholders
        text_parts = ['{"actions": [']
        for i in range(100):
            text_parts.append(f'{{"tool": "write_file", "args": {{"path": "file{i}.py", "content": "WRITE_FILE_CONTENT_file:file{i}.py"}}}},')
        text_parts.append('], "stop_reason": "continue"}\n\n')
        
        for i in range(100):
            text_parts.append(f'---((WRITE_FILE_CONTENT_file:file{i}.py))---\n')
            text_parts.append(f'content for file {i}\n')
        
        text = ''.join(text_parts)
        
        contents = _extract_file_contents(text)
        
        # Should extract all 100 placeholders
        assert len(contents) == 100
        for i in range(100):
            assert f"WRITE_FILE_CONTENT_file:file{i}.py" in contents
