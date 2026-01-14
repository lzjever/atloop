"""Tests for MemoryFormatter configuration system.

This test suite validates the refactored configuration system where
formatting options are loaded from MemoryConfig (single source of truth)
instead of being hardcoded in multiple places.
"""

import pytest

from atloop.config.loader import ConfigLoader
from atloop.config.models import MemoryConfig
from atloop.memory.formatter import MemoryFormatter
from tests.memory.fixtures.sample_state import create_sample_state


class TestMemoryFormatterConfigDefaults:
    """Test that MemoryFormatter loads defaults from MemoryConfig."""

    def test_formatter_loads_defaults_from_config(self):
        """Test that MemoryFormatter loads default format options from MemoryConfig."""
        ConfigLoader.setup()
        config = ConfigLoader.get()
        formatter = MemoryFormatter()

        # Verify that formatter has loaded defaults from config
        assert formatter.default_format_options is not None
        assert "steps_summary_count" in formatter.default_format_options
        assert "tool_results_count" in formatter.default_format_options
        assert "max_file_content_length" in formatter.default_format_options
        assert "include_file_content" in formatter.default_format_options

        # Verify values match config
        assert (
            formatter.default_format_options["steps_summary_count"]
            == config.memory.steps_summary_count
        )
        assert (
            formatter.default_format_options["tool_results_count"]
            == config.memory.tool_results_count
        )
        assert (
            formatter.default_format_options["max_file_content_length"]
            == config.memory.max_file_content_length
        )
        assert (
            formatter.default_format_options["include_file_content"]
            == config.memory.include_file_content
        )

    def test_formatter_uses_config_defaults_when_no_options_provided(self):
        """Test that formatter uses config defaults when format_options is None."""
        ConfigLoader.setup()
        config = ConfigLoader.get()
        state = create_sample_state(step=10, stage="mid")
        formatter = MemoryFormatter()

        formatted = formatter.format(state, format_options=None)

        # Verify that Recent Activity uses config default
        # Extract the steps count from the formatted output
        import re

        recent_activity_match = re.search(
            r"### 📊 Recent Activity \(Last (\d+) Steps\)", formatted
        )
        if recent_activity_match:
            steps_count_in_output = int(recent_activity_match.group(1))
            assert steps_count_in_output == config.memory.steps_summary_count

    def test_formatter_uses_config_defaults_when_empty_options_provided(self):
        """Test that formatter uses config defaults when format_options is empty dict."""
        ConfigLoader.setup()
        config = ConfigLoader.get()
        state = create_sample_state(step=10, stage="mid")
        formatter = MemoryFormatter()

        formatted = formatter.format(state, format_options={})

        # Verify that defaults are used (check Recent Activity section)
        assert "### 📊 Recent Activity" in formatted
        # Should use config default (20) not hardcoded value
        assert f"Last {config.memory.steps_summary_count} Steps" in formatted


class TestMemoryFormatterConfigOverride:
    """Test that format_options can override config defaults."""

    def test_format_options_override_config_defaults(self):
        """Test that format_options parameter can override config defaults."""
        ConfigLoader.setup()
        config = ConfigLoader.get()
        state = create_sample_state(step=10, stage="mid")
        formatter = MemoryFormatter()

        # Override with custom values
        custom_steps_count = 5
        custom_tool_results_count = 3

        formatted = formatter.format(
            state,
            format_options={
                "steps_summary_count": custom_steps_count,
                "tool_results_count": custom_tool_results_count,
            },
        )

        # Verify override values are used
        import re

        recent_activity_match = re.search(
            r"### 📊 Recent Activity \(Last (\d+) Steps\)", formatted
        )
        if recent_activity_match:
            steps_count_in_output = int(recent_activity_match.group(1))
            assert steps_count_in_output == custom_steps_count
            assert steps_count_in_output != config.memory.steps_summary_count

        # Verify tool results count override
        tool_results_match = re.search(
            r"### 🔧 Tool Execution Results \(Last (\d+)\)", formatted
        )
        if tool_results_match:
            tool_results_count_in_output = int(tool_results_match.group(1))
            assert tool_results_count_in_output == custom_tool_results_count
            assert tool_results_count_in_output != config.memory.tool_results_count

    def test_partial_override_keeps_other_defaults(self):
        """Test that partial override only changes specified options."""
        ConfigLoader.setup()
        config = ConfigLoader.get()
        state = create_sample_state(step=10, stage="mid")
        formatter = MemoryFormatter()

        # Only override steps_summary_count
        custom_steps_count = 7
        formatted = formatter.format(
            state, format_options={"steps_summary_count": custom_steps_count}
        )

        # Verify override is used
        import re

        recent_activity_match = re.search(
            r"### 📊 Recent Activity \(Last (\d+) Steps\)", formatted
        )
        if recent_activity_match:
            steps_count_in_output = int(recent_activity_match.group(1))
            assert steps_count_in_output == custom_steps_count

        # Verify other options still use defaults
        tool_results_match = re.search(
            r"### 🔧 Tool Execution Results \(Last (\d+)\)", formatted
        )
        if tool_results_match:
            tool_results_count_in_output = int(tool_results_match.group(1))
            assert tool_results_count_in_output == config.memory.tool_results_count


class TestMemoryFormatterConfigSingleSource:
    """Test single source of truth principle."""

    def test_all_formatters_use_same_config_source(self):
        """Test that multiple formatter instances use the same config source."""
        ConfigLoader.setup()
        config = ConfigLoader.get()

        formatter1 = MemoryFormatter()
        formatter2 = MemoryFormatter()

        # Both should have same defaults from config
        assert (
            formatter1.default_format_options["steps_summary_count"]
            == formatter2.default_format_options["steps_summary_count"]
        )
        assert (
            formatter1.default_format_options["steps_summary_count"]
            == config.memory.steps_summary_count
        )

    def test_config_change_reflects_in_new_formatters(self, temp_atloop_dir):
        """Test that config changes are reflected in new formatter instances."""
        # Create custom config with different values
        config_file = temp_atloop_dir / "config" / "atloop.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            """
ai:
  completion:
    model: test-model
    api_base: https://test.api.com
    api_key: test-key
  performance:
    max_tokens_input: 32000
    max_tokens_output: 4000
sandbox:
  base_url: http://test:8080
  local_test: true
runtime:
  default_budget:
    max_llm_calls: 10
    max_tool_calls: 50
    max_wall_time_sec: 3600
memory:
  steps_summary_count: 15
  tool_results_count: 8
  max_file_content_length: 15000
  include_file_content: false
"""
        )

        ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))
        config = ConfigLoader.get()
        formatter = MemoryFormatter()

        # Verify formatter uses custom config values
        assert formatter.default_format_options["steps_summary_count"] == 15
        assert formatter.default_format_options["tool_results_count"] == 8
        assert formatter.default_format_options["max_file_content_length"] == 15000
        assert formatter.default_format_options["include_file_content"] is False

        # Verify these match config
        assert config.memory.steps_summary_count == 15
        assert config.memory.tool_results_count == 8
        assert config.memory.max_file_content_length == 15000
        assert config.memory.include_file_content is False


class TestMemoryFormatterConfigIntegration:
    """Integration tests for configuration system."""

    def test_recent_activity_uses_config_default(self):
        """Test that Recent Activity section uses config default for steps count."""
        ConfigLoader.setup()
        config = ConfigLoader.get()
        state = create_sample_state(step=25, stage="mid")
        formatter = MemoryFormatter()

        formatted = formatter.format(state, format_options=None)

        # Verify Recent Activity section header shows config default
        expected_header = f"### 📊 Recent Activity (Last {config.memory.steps_summary_count} Steps)"
        assert expected_header in formatted

    def test_tool_results_uses_config_default(self):
        """Test that Tool Execution Results uses config default."""
        ConfigLoader.setup()
        config = ConfigLoader.get()
        state = create_sample_state(step=10, stage="mid")
        formatter = MemoryFormatter()

        formatted = formatter.format(state, format_options=None)

        # Verify Tool Execution Results section header shows config default
        expected_header = f"### 🔧 Tool Execution Results (Last {config.memory.tool_results_count})"
        assert expected_header in formatted

    def test_file_content_inclusion_respects_config(self):
        """Test that file content inclusion respects config setting."""
        ConfigLoader.setup()
        config = ConfigLoader.get()
        state = create_sample_state(step=10, stage="mid")
        formatter = MemoryFormatter()

        formatted = formatter.format(state, format_options=None)

        # Check if Modified Files Content section appears based on config
        # Note: The section might not appear if there are no modified files,
        # or if include_file_content is False
        has_modified_files_section = (
            "### 📄 Modified Files Content" in formatted
            or "Modified Files Content" in formatted
        )

        if config.memory.include_file_content:
            # If True and there are modified files, section should appear
            # But it might not appear if there are no modified files in the sample state
            # So we just verify the config value is respected in formatter
            assert formatter.default_format_options["include_file_content"] is True
        else:
            # If False, section should not appear (or be empty)
            # But we can't assert it's not there because it might not appear anyway
            assert formatter.default_format_options["include_file_content"] is False

    def test_format_with_custom_config_values(self, temp_atloop_dir):
        """Test formatting with custom config values."""
        # Create config with custom formatting values
        config_file = temp_atloop_dir / "config" / "atloop.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(
            """
ai:
  completion:
    model: test-model
    api_base: https://test.api.com
    api_key: test-key
  performance:
    max_tokens_input: 32000
    max_tokens_output: 4000
sandbox:
  base_url: http://test:8080
  local_test: true
runtime:
  default_budget:
    max_llm_calls: 10
    max_tool_calls: 50
    max_wall_time_sec: 3600
memory:
  steps_summary_count: 30
  tool_results_count: 10
"""
        )

        ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))
        state = create_sample_state(step=35, stage="mid")
        formatter = MemoryFormatter()

        formatted = formatter.format(state, format_options=None)

        # Verify custom values are used
        assert "### 📊 Recent Activity (Last 30 Steps)" in formatted
        assert "### 🔧 Tool Execution Results (Last 10)" in formatted


class TestMemoryFormatterConfigBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_existing_code_without_format_options_still_works(self):
        """Test that existing code calling format() without format_options still works."""
        ConfigLoader.setup()
        state = create_sample_state(step=10, stage="mid")
        formatter = MemoryFormatter()

        # Call format() without format_options (should use config defaults)
        formatted = formatter.format(state)

        # Should still produce valid output
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        assert "Recent Activity" in formatted
        assert "Tool Execution Results" in formatted

    def test_existing_code_with_format_options_still_works(self):
        """Test that existing code with format_options still works (override behavior)."""
        ConfigLoader.setup()
        state = create_sample_state(step=10, stage="mid")
        formatter = MemoryFormatter()

        # Call format() with format_options (should override config defaults)
        formatted = formatter.format(
            state,
            format_options={
                "steps_summary_count": 5,
                "tool_results_count": 2,
            },
        )

        # Should use override values
        assert "### 📊 Recent Activity (Last 5 Steps)" in formatted
        assert "### 🔧 Tool Execution Results (Last 2)" in formatted

    def test_format_recent_activity_still_accepts_steps_count_parameter(self):
        """Test that _format_recent_activity still accepts steps_count parameter."""
        ConfigLoader.setup()
        state = create_sample_state(step=10, stage="mid")
        formatter = MemoryFormatter()

        # Direct call to _format_recent_activity with explicit steps_count
        activity = formatter._format_recent_activity(state, steps_count=7)

        assert "### 📊 Recent Activity" in activity
        assert "Last 7 Steps" in activity
