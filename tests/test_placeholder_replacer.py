"""Strict unit tests for PlaceholderReplacer service.

These tests are written based on the interface specification, not implementation details.
They challenge the implementation to ensure correctness and proper error handling.
"""

import pytest

from atloop.orchestrator.phases.placeholder_replacer import (
    PlaceholderReplacementError,
    PlaceholderReplacer,
)


class TestPlaceholderReplacerReplacePlaceholders:
    """Test replace_placeholders method - core replacement logic."""

    def test_replace_write_file_placeholder(self):
        """Test replacing placeholder in write_file action."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "FILE_CONTENT_#1"},
            }
        ]
        file_contents = {"FILE_CONTENT_#1": "def hello():\n    print('world')"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["tool"] == "write_file"
        assert replaced[0]["args"]["path"] == "test.py"
        assert replaced[0]["args"]["content"] == "def hello():\n    print('world')"
        assert len(missing) == 0

    def test_replace_append_file_placeholder(self):
        """Test replacing placeholder in append_file action."""
        actions = [
            {
                "tool": "append_file",
                "args": {"path": "test.py", "content": "FILE_CONTENT_#2"},
            }
        ]
        file_contents = {"FILE_CONTENT_#2": "def goodbye():\n    print('bye')"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["tool"] == "append_file"
        assert replaced[0]["args"]["content"] == "def goodbye():\n    print('bye')"
        assert len(missing) == 0

    def test_replace_edit_file_placeholder(self):
        """Test replacing placeholder in edit_file action."""
        actions = [
            {
                "tool": "edit_file",
                "args": {
                    "path": "test.py",
                    "content": "FILE_CONTENT_#3",
                },
            }
        ]
        file_contents = {
            "FILE_CONTENT_#3": "<old>old code</old><new>new code</new>"
        }

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["tool"] == "edit_file"
        assert (
            replaced[0]["args"]["content"]
            == "<old>old code</old><new>new code</new>"
        )
        assert len(missing) == 0

    def test_replace_multiple_placeholders(self):
        """Test replacing multiple placeholders in different actions."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "FILE_CONTENT_#1"}},
            {"tool": "append_file", "args": {"path": "b.py", "content": "FILE_CONTENT_#2"}},
            {"tool": "edit_file", "args": {"path": "c.py", "content": "FILE_CONTENT_#3"}},
        ]
        file_contents = {
            "FILE_CONTENT_#1": "content1",
            "FILE_CONTENT_#2": "content2",
            "FILE_CONTENT_#3": "content3",
        }

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 3
        assert replaced[0]["args"]["content"] == "content1"
        assert replaced[1]["args"]["content"] == "content2"
        assert replaced[2]["args"]["content"] == "content3"
        assert len(missing) == 0

    def test_missing_placeholder_reported(self):
        """Test that missing placeholders are reported in missing list."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "FILE_CONTENT_#1"},
            }
        ]
        file_contents = {}  # Empty - placeholder not found

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        # Action should still be in list (with unreplaced placeholder)
        assert replaced[0]["args"]["content"] == "FILE_CONTENT_#1"
        assert len(missing) == 1
        assert "FILE_CONTENT_#1" in missing

    def test_multiple_missing_placeholders(self):
        """Test reporting multiple missing placeholders."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "FILE_CONTENT_#1"}},
            {"tool": "append_file", "args": {"path": "b.py", "content": "FILE_CONTENT_#2"}},
        ]
        file_contents = {}  # Both missing

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 2
        assert len(missing) == 2
        assert "FILE_CONTENT_#1" in missing
        assert "FILE_CONTENT_#2" in missing

    def test_non_placeholder_content_unchanged(self):
        """Test that non-placeholder content is left unchanged."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "actual content"},
            }
        ]
        file_contents = {"FILE_CONTENT_#1": "replacement"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "actual content"
        assert len(missing) == 0

    def test_non_content_tool_unchanged(self):
        """Test that tools not using content placeholders are unchanged."""
        actions = [
            {"tool": "run", "args": {"cmd": "echo hello"}},
            {"tool": "read_file", "args": {"path": "test.py"}},
        ]
        file_contents = {"FILE_CONTENT_#1": "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 2
        assert replaced[0]["tool"] == "run"
        assert replaced[1]["tool"] == "read_file"
        assert len(missing) == 0

    def test_empty_actions_list(self):
        """Test handling empty actions list."""
        actions = []
        file_contents = {"FILE_CONTENT_#1": "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 0
        assert len(missing) == 0

    def test_empty_file_contents(self):
        """Test handling empty file_contents dict."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "FILE_CONTENT_#1"},
            }
        ]
        file_contents = {}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "FILE_CONTENT_#1"  # Unreplaced
        assert len(missing) == 1

    def test_immutability_original_unchanged(self):
        """Test that original actions are not modified (immutability)."""
        original_action = {
            "tool": "write_file",
            "args": {"path": "test.py", "content": "FILE_CONTENT_#1"},
        }
        actions = [original_action]
        file_contents = {"FILE_CONTENT_#1": "replaced content"}

        replaced, _ = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        # Original should be unchanged
        assert original_action["args"]["content"] == "FILE_CONTENT_#1"
        # Replaced should have new content
        assert replaced[0]["args"]["content"] == "replaced content"
        # They should be different objects
        assert replaced[0] is not original_action
        assert replaced[0]["args"] is not original_action["args"]

    def test_immutability_nested_structure(self):
        """Test immutability with nested action structure."""
        original_action = {
            "tool": "edit_file",
            "args": {
                "path": "test.py",
                "content": "FILE_CONTENT_#1",
                "replace_all": False,
            },
        }
        actions = [original_action]
        file_contents = {"FILE_CONTENT_#1": "new content"}

        replaced, _ = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        # Original args should be unchanged
        assert original_action["args"]["content"] == "FILE_CONTENT_#1"
        assert original_action["args"]["replace_all"] is False
        # Replaced should have new content but same other args
        assert replaced[0]["args"]["content"] == "new content"
        assert replaced[0]["args"]["replace_all"] is False
        # Args dicts should be different objects
        assert replaced[0]["args"] is not original_action["args"]

    def test_partial_replacement_mixed_placeholders(self):
        """Test scenario where some placeholders exist, some don't."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "FILE_CONTENT_#1"}},
            {"tool": "write_file", "args": {"path": "b.py", "content": "FILE_CONTENT_#2"}},
        ]
        file_contents = {"FILE_CONTENT_#1": "content1"}  # #2 missing

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 2
        assert replaced[0]["args"]["content"] == "content1"  # Replaced
        assert replaced[1]["args"]["content"] == "FILE_CONTENT_#2"  # Unreplaced
        assert len(missing) == 1
        assert "FILE_CONTENT_#2" in missing

    def test_placeholder_with_special_characters(self):
        """Test placeholder replacement with special characters in content."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "FILE_CONTENT_#1"},
            }
        ]
        file_contents = {
            "FILE_CONTENT_#1": "<old>line1\nline2\tline3</old><new>new1\nnew2</new>"
        }

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert "\n" in replaced[0]["args"]["content"]
        assert "\t" in replaced[0]["args"]["content"]
        assert len(missing) == 0

    def test_very_large_content(self):
        """Test replacement with very large content."""
        large_content = "x" * 100000  # 100KB
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "FILE_CONTENT_#1"},
            }
        ]
        file_contents = {"FILE_CONTENT_#1": large_content}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert len(replaced[0]["args"]["content"]) == 100000
        assert replaced[0]["args"]["content"] == large_content
        assert len(missing) == 0


class TestPlaceholderReplacerValidateReplacement:
    """Test validate_replacement method - validation logic."""

    def test_validate_all_replaced(self):
        """Test validation passes when all placeholders are replaced."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "actual content"}},
            {"tool": "run", "args": {"cmd": "echo hello"}},
        ]

        is_valid, remaining = PlaceholderReplacer.validate_replacement(actions, {})

        assert is_valid is True
        assert len(remaining) == 0

    def test_validate_unreplaced_placeholder_detected(self):
        """Test validation detects unreplaced placeholders."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "FILE_CONTENT_#1"},
            }
        ]

        is_valid, remaining = PlaceholderReplacer.validate_replacement(actions, {})

        assert is_valid is False
        assert len(remaining) == 1
        assert "FILE_CONTENT_#1" in remaining[0]

    def test_validate_multiple_unreplaced(self):
        """Test validation detects multiple unreplaced placeholders."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "FILE_CONTENT_#1"}},
            {"tool": "append_file", "args": {"path": "b.py", "content": "FILE_CONTENT_#2"}},
            {"tool": "edit_file", "args": {"path": "c.py", "content": "FILE_CONTENT_#3"}},
        ]

        is_valid, remaining = PlaceholderReplacer.validate_replacement(actions, {})

        assert is_valid is False
        assert len(remaining) == 3
        # Check that all are reported
        remaining_str = " ".join(remaining)
        assert "FILE_CONTENT_#1" in remaining_str
        assert "FILE_CONTENT_#2" in remaining_str
        assert "FILE_CONTENT_#3" in remaining_str

    def test_validate_ignores_non_content_tools(self):
        """Test validation ignores tools that don't use content placeholders."""
        actions = [
            {"tool": "run", "args": {"cmd": "echo hello"}},
            {"tool": "read_file", "args": {"path": "test.py"}},
        ]

        is_valid, remaining = PlaceholderReplacer.validate_replacement(actions, {})

        assert is_valid is True
        assert len(remaining) == 0

    def test_validate_mixed_replaced_and_unreplaced(self):
        """Test validation with mix of replaced and unreplaced."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "actual content"}},
            {"tool": "write_file", "args": {"path": "b.py", "content": "FILE_CONTENT_#1"}},
        ]

        is_valid, remaining = PlaceholderReplacer.validate_replacement(actions, {})

        assert is_valid is False
        assert len(remaining) == 1
        assert "FILE_CONTENT_#1" in remaining[0]

    def test_validate_empty_actions(self):
        """Test validation with empty actions list."""
        actions = []

        is_valid, remaining = PlaceholderReplacer.validate_replacement(actions, {})

        assert is_valid is True
        assert len(remaining) == 0


class TestPlaceholderReplacerReplaceAndValidate:
    """Test replace_and_validate method - combined replacement and validation."""

    def test_replace_and_validate_success(self):
        """Test successful replacement and validation."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "FILE_CONTENT_#1"},
            }
        ]
        file_contents = {"FILE_CONTENT_#1": "actual content"}

        replaced = PlaceholderReplacer.replace_and_validate(actions, file_contents, strict=False)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "actual content"

    def test_replace_and_validate_strict_mode_raises_error(self):
        """Test that strict mode raises exception on missing placeholders."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "FILE_CONTENT_#1"},
            }
        ]
        file_contents = {}  # Missing

        with pytest.raises(PlaceholderReplacementError) as exc_info:
            PlaceholderReplacer.replace_and_validate(actions, file_contents, strict=True)

        assert len(exc_info.value.missing_placeholders) == 1
        assert "FILE_CONTENT_#1" in exc_info.value.missing_placeholders

    def test_replace_and_validate_non_strict_mode_logs_warning(self):
        """Test that non-strict mode returns actions even with missing placeholders."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "FILE_CONTENT_#1"},
            }
        ]
        file_contents = {}  # Missing

        # Should not raise, but return actions with unreplaced placeholder
        replaced = PlaceholderReplacer.replace_and_validate(
            actions, file_contents, strict=False
        )

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "FILE_CONTENT_#1"  # Still unreplaced

    def test_replace_and_validate_multiple_actions(self):
        """Test replace_and_validate with multiple actions."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "FILE_CONTENT_#1"}},
            {"tool": "append_file", "args": {"path": "b.py", "content": "FILE_CONTENT_#2"}},
            {"tool": "run", "args": {"cmd": "echo hello"}},
        ]
        file_contents = {
            "FILE_CONTENT_#1": "content1",
            "FILE_CONTENT_#2": "content2",
        }

        replaced = PlaceholderReplacer.replace_and_validate(actions, file_contents, strict=False)

        assert len(replaced) == 3
        assert replaced[0]["args"]["content"] == "content1"
        assert replaced[1]["args"]["content"] == "content2"
        assert replaced[2]["tool"] == "run"  # Unchanged

    def test_replace_and_validate_strict_mode_multiple_missing(self):
        """Test strict mode with multiple missing placeholders."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "FILE_CONTENT_#1"}},
            {"tool": "write_file", "args": {"path": "b.py", "content": "FILE_CONTENT_#2"}},
        ]
        file_contents = {}  # Both missing

        with pytest.raises(PlaceholderReplacementError) as exc_info:
            PlaceholderReplacer.replace_and_validate(actions, file_contents, strict=True)

        assert len(exc_info.value.missing_placeholders) == 2
        assert "FILE_CONTENT_#1" in exc_info.value.missing_placeholders
        assert "FILE_CONTENT_#2" in exc_info.value.missing_placeholders


class TestPlaceholderReplacerEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_placeholder_with_different_numbering(self):
        """Test placeholders with different numbers."""
        actions = [
            {"tool": "write_file", "args": {"path": "a.py", "content": "FILE_CONTENT_#1"}},
            {"tool": "write_file", "args": {"path": "b.py", "content": "FILE_CONTENT_#99"}},
        ]
        file_contents = {
            "FILE_CONTENT_#1": "content1",
            "FILE_CONTENT_#99": "content99",
        }

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 2
        assert replaced[0]["args"]["content"] == "content1"
        assert replaced[1]["args"]["content"] == "content99"
        assert len(missing) == 0

    def test_content_not_string_type(self):
        """Test handling when content is not a string (should not crash)."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": 12345}},
        ]
        file_contents = {"FILE_CONTENT_#1": "content"}

        # Should not crash - non-string content should be left as-is
        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == 12345
        assert len(missing) == 0

    def test_missing_args_key(self):
        """Test handling when args key is missing."""
        actions = [{"tool": "write_file"}]  # Missing "args" key
        file_contents = {"FILE_CONTENT_#1": "content"}

        # Should not crash - should handle gracefully
        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert len(missing) == 0

    def test_missing_content_key_in_args(self):
        """Test handling when content key is missing in args."""
        actions = [{"tool": "write_file", "args": {"path": "test.py"}}]  # Missing "content"
        file_contents = {"FILE_CONTENT_#1": "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert "content" not in replaced[0]["args"]
        assert len(missing) == 0

    def test_empty_string_content(self):
        """Test handling empty string content."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": ""}},
        ]
        file_contents = {"FILE_CONTENT_#1": "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == ""  # Empty string is not a placeholder
        assert len(missing) == 0

    def test_placeholder_like_string_but_not_placeholder(self):
        """Test strings that look like placeholders but aren't."""
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "FILE_CONTENT_#X"}},  # X not a number
            {"tool": "write_file", "args": {"path": "test2.py", "content": "FILE_CONTENT"}},  # Missing #N
        ]
        file_contents = {"FILE_CONTENT_#1": "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 2
        # These should not be treated as placeholders
        assert replaced[0]["args"]["content"] == "FILE_CONTENT_#X"
        assert replaced[1]["args"]["content"] == "FILE_CONTENT"
        assert len(missing) == 0

    def test_unicode_content(self):
        """Test replacement with unicode content."""
        unicode_content = "你好世界\nこんにちは\n안녕하세요"
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": "FILE_CONTENT_#1"}},
        ]
        file_contents = {"FILE_CONTENT_#1": unicode_content}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == unicode_content
        assert len(missing) == 0

    def test_very_long_placeholder_name(self):
        """Test with very long placeholder name (edge case)."""
        # This tests the startswith check doesn't break with edge cases
        long_placeholder = "FILE_CONTENT_#" + "1" * 1000
        actions = [
            {"tool": "write_file", "args": {"path": "test.py", "content": long_placeholder}},
        ]
        file_contents = {long_placeholder: "content"}

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert replaced[0]["args"]["content"] == "content"
        assert len(missing) == 0
