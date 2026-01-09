"""Integration tests for CLI commands using real configuration."""

import logging
from pathlib import Path

import pytest

from atloop.cli.commands.config import cmd_config
from atloop.cli.commands.init import cmd_init

pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)


class TestCLIIntegration:
    """Integration tests for CLI commands with real config."""

    def test_cmd_config_with_real_config(self, real_config_file: Path):
        """Test config command with real configuration."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing cmd_config with real config")

        # Create mock args
        class MockArgs:
            atloop_dir = None

        args = MockArgs()

        # Should not raise exception
        # Note: cmd_config prints to stdout, so we just verify it doesn't crash
        try:
            result = cmd_config(args)
            assert result == 0
            logger.info("cmd_config executed successfully")
        except Exception as e:
            logger.error(f"cmd_config failed: {e}")
            raise

    def test_cmd_init_with_real_config(self, real_config_file: Path):
        """Test init command with real configuration."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing cmd_init with real config")

        # Create mock args
        class MockArgs:
            atloop_dir = None

        args = MockArgs()

        # Should not raise exception
        try:
            result = cmd_init(args)
            assert result == 0
            logger.info("cmd_init executed successfully")
        except Exception as e:
            logger.error(f"cmd_init failed: {e}")
            raise

    def test_cmd_config_with_custom_dir(self, temp_atloop_dir: Path):
        """Test config command with custom atloop directory."""
        # Create minimal config
        config_file = temp_atloop_dir / "config" / "atloop.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("""
ai:
  completion:
    model: test-model
    api_base: https://test.api.com
    api_key: test-key
  performance:
    max_tokens_input: 1000
    max_tokens_output: 500
sandbox:
  base_url: http://test:8080
  local_test: true
default_budget:
  max_llm_calls: 10
  max_tool_calls: 50
  max_wall_time_sec: 3600
""")

        # Create mock args
        class MockArgs:
            atloop_dir = str(temp_atloop_dir)

        args = MockArgs()

        # Should not raise exception
        try:
            result = cmd_config(args)
            assert result == 0
            logger.info("cmd_config with custom dir executed successfully")
        except Exception as e:
            logger.error(f"cmd_config with custom dir failed: {e}")
            raise
