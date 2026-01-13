"""Tests for placeholder uniqueness validation in PlanPhase.

These tests verify that duplicate placeholder names are detected and rejected
in the same round of actions.
"""

import pytest

from atloop.orchestrator.phases.placeholder_info import PlaceholderInfoTracker
from atloop.orchestrator.phases.placeholder_replacer import PlaceholderReplacer


class TestPlaceholderUniquenessValidation:
    """Test placeholder name uniqueness validation logic."""

    def test_duplicate_placeholder_names_same_type(self):
        """Test that duplicate placeholder names of same type are detected."""
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

        # Extract placeholder info
        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)

        # Check for duplicates
        placeholder_names = [info.placeholder for info in placeholder_info if info.placeholder]
        assert len(placeholder_names) == 2
        assert placeholder_names[0] == placeholder_names[1]  # Duplicate detected

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

        placeholder_names = [info.placeholder for info in placeholder_info if info.placeholder]
        assert len(placeholder_names) == 2
        assert placeholder_names[0] != placeholder_names[1]  # Unique

    def test_duplicate_across_different_tools(self):
        """Test that same placeholder name across different tools is still duplicate."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },
            {
                "tool": "edit_file",
                "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },  # Same name, different tool
        ]

        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)

        placeholder_names = [info.placeholder for info in placeholder_info if info.placeholder]
        assert len(placeholder_names) == 2
        assert placeholder_names[0] == placeholder_names[1]  # Still duplicate (same full name)

    def test_different_types_same_descriptive_name_allowed(self):
        """Test that different types with same descriptive part are allowed (full names differ)."""
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

        placeholder_names = [info.placeholder for info in placeholder_info if info.placeholder]
        assert len(placeholder_names) == 2
        # Full names are different (different prefix), so should be unique
        assert placeholder_names[0] != placeholder_names[1]

    def test_multiple_duplicates_detected(self):
        """Test that multiple duplicates are all detected."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },
            {
                "tool": "write_file",
                "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },  # Duplicate 1
            {
                "tool": "write_file",
                "args": {"path": "c.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },  # Duplicate 2
        ]

        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)

        placeholder_names = [info.placeholder for info in placeholder_info if info.placeholder]
        assert len(placeholder_names) == 3
        # All three are the same
        assert placeholder_names[0] == placeholder_names[1] == placeholder_names[2]

    def test_no_placeholders_no_duplicates(self):
        """Test that actions without placeholders don't cause duplicate issues."""
        actions = [
            {"tool": "read_file", "args": {"path": "a.py"}},
            {"tool": "read_file", "args": {"path": "b.py"}},
        ]

        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)

        placeholder_names = [info.placeholder for info in placeholder_info if info.placeholder]
        assert len(placeholder_names) == 0  # No placeholders

    def test_mixed_placeholders_and_non_placeholders(self):
        """Test uniqueness check with mix of placeholders and non-placeholders."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:a.py"},
            },
            {"tool": "read_file", "args": {"path": "b.py"}},  # No placeholder
            {
                "tool": "write_file",
                "args": {"path": "c.py", "content": "WRITE_FILE_CONTENT_file:c.py"},
            },
        ]

        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)

        placeholder_names = [info.placeholder for info in placeholder_info if info.placeholder]
        assert len(placeholder_names) == 2
        assert placeholder_names[0] != placeholder_names[1]  # Unique

    def test_duplicate_with_special_characters(self):
        """Test duplicate detection with special characters in names."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file: test.py (backup)"},
            },
            {
                "tool": "write_file",
                "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file: test.py (backup)"},
            },  # Duplicate
        ]

        placeholder_info = PlaceholderInfoTracker.extract_placeholder_info(actions)

        placeholder_names = [info.placeholder for info in placeholder_info if info.placeholder]
        assert len(placeholder_names) == 2
        assert (
            placeholder_names[0] == placeholder_names[1]
        )  # Duplicate detected even with special chars


class TestPlaceholderUniquenessInPlanPhase:
    """Test placeholder uniqueness validation as it would be done in PlanPhase."""

    def test_validate_uniqueness_logic(self):
        """Test the uniqueness validation logic that PlanPhase would use."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },
            {
                "tool": "write_file",
                "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },  # Duplicate
        ]

        # Simulate PlanPhase validation logic
        placeholder_names = []
        duplicate_found = False
        duplicate_action_index = None
        duplicate_name = None

        for i, action in enumerate(actions):
            tool = action.get("tool", "")
            args = action.get("args", {})
            field_name, value = PlaceholderReplacer.get_placeholder_field_value(tool, args)
            if field_name and PlaceholderReplacer._is_valid_placeholder(value):
                if value in placeholder_names:
                    # Duplicate found - this is what PlanPhase should detect
                    duplicate_found = True
                    duplicate_action_index = i + 1
                    duplicate_name = value
                    break  # Stop on first duplicate
                placeholder_names.append(value)

        # Verify that duplicate was detected
        assert duplicate_found is True, "Duplicate should have been detected"
        assert duplicate_action_index == 2, (
            f"Duplicate should be in action 2, got {duplicate_action_index}"
        )
        assert duplicate_name == "WRITE_FILE_CONTENT_file:test.py"
        assert len(placeholder_names) == 1  # Only first one was added before duplicate detected

    def test_validate_uniqueness_unique_names(self):
        """Test uniqueness validation with unique names."""
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

        placeholder_names = []
        for i, action in enumerate(actions):
            tool = action.get("tool", "")
            args = action.get("args", {})
            field_name, value = PlaceholderReplacer.get_placeholder_field_value(tool, args)
            if field_name and PlaceholderReplacer._is_valid_placeholder(value):
                if value in placeholder_names:
                    pytest.fail(f"Duplicate placeholder '{value}' found in action {i + 1}")
                placeholder_names.append(value)

        assert len(placeholder_names) == 2
        assert placeholder_names[0] != placeholder_names[1]  # Unique
