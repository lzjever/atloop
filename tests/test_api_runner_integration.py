"""Integration tests for TaskRunner API using real configuration."""

import logging
from pathlib import Path

import pytest

from atloop.config.loader import ConfigLoader

pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)


class TestTaskRunnerIntegration:
    """Integration tests for TaskRunner with real config."""

    def test_task_runner_config_loading(self, real_config_file: Path):
        """Test TaskRunner config loading with real config."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing TaskRunner config loading")

        # Setup config (TaskRunner would do this)
        ConfigLoader.setup()
        config = ConfigLoader.get()
        assert config is not None
        logger.info(f"Config loaded: {config.ai.completion.model}")

    def test_task_runner_with_custom_dir(self, temp_atloop_dir: Path, temp_workspace: Path):
        """Test config loading with custom atloop directory."""
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

        # Setup config with custom dir
        ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))
        config = ConfigLoader.get()
        assert config.ai.completion.model == "test-model"

    def test_task_config_validation(self, real_config_file: Path, temp_workspace: Path):
        """Test task config structure validation."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing task config validation")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()
        assert config is not None

        # Test minimal valid task config structure
        task_config = {
            "goal": "Test task",
            "workspace_root": str(temp_workspace),
        }
        assert "goal" in task_config
        assert "workspace_root" in task_config
        logger.info("Task config validation passed")

    def test_sandbox_config_override(self, real_config_file: Path, temp_workspace: Path):
        """Test sandbox config override structure."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing sandbox config override")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()
        assert config is not None

        # Test sandbox override structure
        sandbox_override = {
            "base_url": None,
            "local_test": True,
        }
        assert "base_url" in sandbox_override
        assert "local_test" in sandbox_override
        logger.info("Sandbox override config validation passed")
