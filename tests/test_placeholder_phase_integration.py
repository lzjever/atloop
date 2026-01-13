"""Integration tests for placeholder handling across PlanPhase and ActPhase.

Tests cover:
1. Placeholder info extraction in PlanPhase
2. Placeholder info storage in job_state
3. Placeholder info retrieval in ActPhase
4. Memory recording with placeholder names
5. Error handling for duplicate placeholders
6. Error handling for missing placeholders
"""

from atloop.orchestrator.job_state import JobState
from atloop.orchestrator.phases.placeholder_info import PlaceholderInfoTracker
from atloop.orchestrator.phases.placeholder_replacer import PlaceholderReplacer


class TestPlaceholderInfoFlowPlanToAct:
    """Test placeholder info flow from PlanPhase to ActPhase."""

    def test_placeholder_info_stored_in_job_state(self):
        """Test that placeholder info is stored in job_state by PlanPhase logic."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "a.py", "content": "WRITE_FILE_CONTENT_file:a.py"},
            },
            {
                "tool": "write_file",
                "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:b.py"},
            },
            {"tool": "read_file", "args": {"path": "c.py"}},  # No placeholder
        ]

        # Simulate PlanPhase logic
        placeholder_info_list = PlaceholderInfoTracker.extract_placeholder_info(actions)
        placeholder_info_dict = {
            i: {
                "tool": info.tool,
                "placeholder": info.placeholder,
                "args": info.args,
            }
            for i, info in enumerate(placeholder_info_list)
        }

        # Verify structure
        assert len(placeholder_info_dict) == 3
        assert placeholder_info_dict[0]["placeholder"] == "WRITE_FILE_CONTENT_file:a.py"
        assert placeholder_info_dict[0]["args"] is None
        assert placeholder_info_dict[1]["placeholder"] == "WRITE_FILE_CONTENT_file:b.py"
        assert placeholder_info_dict[1]["args"] is None
        assert placeholder_info_dict[2]["placeholder"] is None
        assert placeholder_info_dict[2]["args"] == {"path": "c.py"}

    def test_placeholder_info_retrieved_in_act_phase(self):
        """Test that ActPhase can retrieve placeholder info from job_state."""
        # Simulate what PlanPhase would store
        job_state = JobState()
        job_state.shared_data["placeholder_info"] = {
            0: {
                "tool": "write_file",
                "placeholder": "WRITE_FILE_CONTENT_file:test.py",
                "args": None,
            },
            1: {
                "tool": "read_file",
                "placeholder": None,
                "args": {"path": "test.py"},
            },
        }

        # Simulate ActPhase retrieval
        placeholder_info_dict = job_state.shared_data.get("placeholder_info", {})

        assert len(placeholder_info_dict) == 2
        assert placeholder_info_dict[0]["placeholder"] == "WRITE_FILE_CONTENT_file:test.py"
        assert placeholder_info_dict[1]["placeholder"] is None
        assert placeholder_info_dict[1]["args"] == {"path": "test.py"}

    def test_placeholder_info_matching_with_sorted_actions(self):
        """Test that placeholder info matches correctly even when actions are sorted."""
        # PlanPhase stores by original index
        original_actions = [
            {"tool": "read_file", "args": {"path": "a.py"}},
            {
                "tool": "write_file",
                "args": {"path": "b.py", "content": "WRITE_FILE_CONTENT_file:b.py"},
            },
            {
                "tool": "edit_file",
                "args": {"path": "c.py", "content": "EDIT_FILE_CONTENT_file:c.py"},
            },
        ]

        placeholder_info_list = PlaceholderInfoTracker.extract_placeholder_info(original_actions)
        placeholder_info_dict = {
            i: {
                "tool": info.tool,
                "placeholder": info.placeholder,
                "args": info.args,
            }
            for i, info in enumerate(placeholder_info_list)
        }

        # ActPhase sorts actions (write_file first)
        sorted_actions = sorted(
            original_actions, key=lambda a: (a.get("tool") != "write_file", a.get("tool"))
        )

        # Match by finding original index
        for sorted_action in sorted_actions:
            original_index = original_actions.index(sorted_action)
            placeholder_data = placeholder_info_dict.get(original_index, {})

            # Verify we can retrieve the correct info
            assert placeholder_data["tool"] == sorted_action["tool"]


class TestPlaceholderUniquenessInPlanPhase:
    """Test uniqueness validation in PlanPhase context."""

    def test_duplicate_detection_raises_error(self):
        """Test that duplicate placeholder names are detected and cause error."""
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

        # Simulate PlanPhase validation
        placeholder_names = []
        duplicate_found = False
        duplicate_action_index = None

        for i, action in enumerate(actions):
            tool = action.get("tool", "")
            args = action.get("args", {})
            field_name, value = PlaceholderReplacer.get_placeholder_field_value(tool, args)
            if field_name and PlaceholderReplacer._is_valid_placeholder(value):
                if value in placeholder_names:
                    duplicate_found = True
                    duplicate_action_index = i + 1
                    break
                placeholder_names.append(value)

        assert duplicate_found is True
        assert duplicate_action_index == 2

    def test_unique_names_pass_validation(self):
        """Test that unique placeholder names pass validation."""
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
        duplicate_found = False

        for i, action in enumerate(actions):
            tool = action.get("tool", "")
            args = action.get("args", {})
            field_name, value = PlaceholderReplacer.get_placeholder_field_value(tool, args)
            if field_name and PlaceholderReplacer._is_valid_placeholder(value):
                if value in placeholder_names:
                    duplicate_found = True
                    break
                placeholder_names.append(value)

        assert duplicate_found is False
        assert len(placeholder_names) == 2


class TestPlaceholderMemoryRecording:
    """Test memory recording with placeholder information."""

    def test_tool_results_history_format_with_placeholder(self):
        """Test tool_results_history record format when placeholder is used."""
        # Simulate what ActPhase creates
        tool_result_record = {
            "step": 1,
            "tool": "write_file",
            "args": None,  # None when placeholder was used
            "placeholder": "WRITE_FILE_CONTENT_file:test.py",
            "result": {
                "ok": True,
                "success": True,
                "stdout": "File created",
                "stderr": "",
            },
        }

        # Verify format
        assert "step" in tool_result_record
        assert "tool" in tool_result_record
        assert "placeholder" in tool_result_record
        assert "result" in tool_result_record
        assert tool_result_record["placeholder"] is not None
        assert tool_result_record["args"] is None

    def test_tool_results_history_format_without_placeholder(self):
        """Test tool_results_history record format when no placeholder is used."""
        tool_result_record = {
            "step": 1,
            "tool": "read_file",
            "args": {"path": "test.py"},  # Actual args when no placeholder
            "placeholder": None,
            "result": {
                "ok": True,
                "stdout": "file content",
                "stderr": "",
            },
        }

        # Verify format
        assert tool_result_record["placeholder"] is None
        assert tool_result_record["args"] is not None
        assert tool_result_record["args"]["path"] == "test.py"

    def test_memory_records_mixed_scenarios(self):
        """Test memory records with mix of placeholders and direct args."""
        records = [
            {
                "step": 1,
                "tool": "write_file",
                "args": None,
                "placeholder": "WRITE_FILE_CONTENT_file:a.py",
                "result": {"ok": True},
            },
            {
                "step": 1,
                "tool": "read_file",
                "args": {"path": "a.py"},
                "placeholder": None,
                "result": {"ok": True},
            },
            {
                "step": 1,
                "tool": "run",
                "args": None,
                "placeholder": "SHELL_COMMAND_cmd:python3-a.py",
                "result": {"ok": True},
            },
        ]

        # Verify all records have correct structure
        for record in records:
            assert "step" in record
            assert "tool" in record
            assert "placeholder" in record
            assert "result" in record
            # If placeholder exists, args should be None; otherwise args should exist
            if record["placeholder"]:
                assert record["args"] is None
            else:
                assert record["args"] is not None


class TestPlaceholderErrorScenarios:
    """Test error scenarios in placeholder handling."""

    def test_missing_placeholder_in_file_contents(self):
        """Test handling when placeholder is referenced but not in file_contents."""
        actions = [
            {
                "tool": "write_file",
                "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"},
            },
        ]
        file_contents = {}  # Missing

        replaced, missing = PlaceholderReplacer.replace_placeholders(actions, file_contents)

        assert len(replaced) == 1
        assert (
            replaced[0]["args"]["content"] == "WRITE_FILE_CONTENT_file:test.py"
        )  # Still unreplaced
        assert len(missing) == 1
        assert "WRITE_FILE_CONTENT_file:test.py" in missing

    def test_type_mismatch_detection(self):
        """Test that placeholder type mismatches are detected."""

        # Should detect type mismatch
        is_valid, error_msg = PlaceholderReplacer._validate_placeholder_type(
            "write_file", "EDIT_FILE_CONTENT_file:test.py"
        )

        assert is_valid is False
        assert "mismatch" in error_msg.lower() or "expects" in error_msg.lower()

    def test_run_tool_without_placeholder_detected(self):
        """Test that run tool without placeholder is detected."""
        actions = [
            {"tool": "run", "args": {"cmd": "ls -la"}},  # Direct command
        ]

        is_valid, error_msg, action_index = PlaceholderInfoTracker.validate_run_tool_placeholders(
            actions
        )

        assert is_valid is False
        assert error_msg is not None
        assert "must use SHELL_COMMAND" in error_msg
        assert action_index == 1

    def test_duplicate_placeholder_causes_error(self):
        """Test that duplicate placeholder names cause validation error."""
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

        # Simulate PlanPhase validation
        placeholder_names = []
        error_occurred = False

        for i, action in enumerate(actions):
            tool = action.get("tool", "")
            args = action.get("args", {})
            field_name, value = PlaceholderReplacer.get_placeholder_field_value(tool, args)
            if field_name and PlaceholderReplacer._is_valid_placeholder(value):
                if value in placeholder_names:
                    error_occurred = True
                    break
                placeholder_names.append(value)

        assert error_occurred is True


class TestPlaceholderExtractionEdgeCases:
    """Test edge cases in placeholder extraction."""

    def test_extract_with_placeholder_at_text_start(self):
        """Test extraction when placeholder is at the very start of text."""
        text = """---((WRITE_FILE_CONTENT_file:test.py))---
def hello():
    pass
"""
        from atloop.llm.schema import _extract_file_contents

        contents = _extract_file_contents(text)

        assert len(contents) == 1
        assert "WRITE_FILE_CONTENT_file:test.py" in contents

    def test_extract_with_placeholder_at_text_end(self):
        """Test extraction when placeholder is at the very end of text."""
        text = """Some text before
---((WRITE_FILE_CONTENT_file:test.py))---
content"""
        from atloop.llm.schema import _extract_file_contents

        contents = _extract_file_contents(text)

        assert len(contents) == 1
        assert contents["WRITE_FILE_CONTENT_file:test.py"] == "content"

    def test_extract_with_only_newlines_between_placeholders(self):
        """Test extraction when placeholders are separated only by newlines."""
        text = """---((WRITE_FILE_CONTENT_file:a.py))---

---((WRITE_FILE_CONTENT_file:b.py))---
content
"""
        from atloop.llm.schema import _extract_file_contents

        contents = _extract_file_contents(text)

        assert len(contents) == 2
        assert "WRITE_FILE_CONTENT_file:a.py" in contents
        assert "WRITE_FILE_CONTENT_file:b.py" in contents
        # First should have empty or whitespace content
        assert contents["WRITE_FILE_CONTENT_file:a.py"].strip() == ""

    def test_extract_requires_placeholder_at_line_start(self):
        """Test that placeholder must be at line start (not indented)."""
        # Placeholder with leading spaces should NOT match (by design)
        text = """   ---((WRITE_FILE_CONTENT_file:test.py))---
   content with indentation
"""
        from atloop.llm.schema import _extract_file_contents

        contents = _extract_file_contents(text)

        # Should NOT extract (placeholder must be at line start)
        assert len(contents) == 0

    def test_extract_preserves_content_exactly_as_is(self):
        """Test that content is extracted exactly as-is without any modification."""
        text = """
---((WRITE_FILE_CONTENT_file:test.py))---
   content with indentation
   more content
"""
        from atloop.llm.schema import _extract_file_contents

        contents = _extract_file_contents(text)

        # Should extract content exactly as-is (preserve all whitespace, indentation, etc.)
        assert len(contents) == 1
        content = contents["WRITE_FILE_CONTENT_file:test.py"]
        # Content should preserve leading whitespace and indentation
        assert content.startswith("   content") or content.startswith("\n   content")
        assert "content with indentation" in content
        assert "more content" in content
        # Internal indentation should be preserved exactly
        assert "   more content" in content
        # Leading whitespace should be preserved (critical for Python code indentation)
        assert content.strip() != content  # Should have leading/trailing whitespace

    def test_remove_sections_handles_nested_brackets_in_content(self):
        """Test that removal handles content with nested bracket-like patterns."""
        text = """{
  "actions": [{"tool": "write_file", "args": {"path": "test.py", "content": "WRITE_FILE_CONTENT_file:test.py"}}],
  "stop_reason": "continue"
}

---((WRITE_FILE_CONTENT_file:test.py))---
def func():
    # Comment with ((nested)) brackets
    if x > 0:
        return ((value))
"""
        from atloop.llm.schema import _remove_file_content_sections

        result = _remove_file_content_sections(text)

        # Should remove placeholder section but preserve JSON
        assert "---((WRITE_FILE_CONTENT_file:test.py))---" not in result
        assert '"stop_reason": "continue"' in result
        assert "((nested))" not in result  # Should be removed with content
        assert "((value))" not in result  # Should be removed with content
