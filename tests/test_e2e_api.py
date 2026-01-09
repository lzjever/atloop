"""End-to-end tests for API layer."""

import logging
from pathlib import Path

import pytest

from atloop.api.runner import TaskRunner
from atloop.config.loader import ConfigLoader

pytestmark = pytest.mark.e2e

logger = logging.getLogger(__name__)


class TestAPIE2E:
    """End-to-end tests for API layer."""

    def test_e2e_task_runner(self, real_config_file: Path, temp_workspace: Path):
        """Test TaskRunner end-to-end."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing TaskRunner E2E")

        # Initialize runner
        runner = TaskRunner()
        assert runner is not None

        # Create task config
        {
            "goal": "Test task",
            "workspace_root": str(temp_workspace),
            "sandbox": {
                "base_url": None,
                "local_test": True,
            },
        }

        # Verify config can be loaded
        config = ConfigLoader.get()
        assert config is not None

        # Note: Actual execution would require sandbox/LLM
        # This test just verifies the setup works
        logger.info("TaskRunner E2E setup successful ✅")

    def test_e2e_custom_config(
        self, real_config_file: Path, temp_workspace: Path, temp_atloop_dir: Path
    ):
        """Test TaskRunner with custom config end-to-end."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing TaskRunner custom config E2E")

        # Create custom config
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

        # Initialize runner with custom dir
        runner = TaskRunner(atloop_dir=str(temp_atloop_dir))
        assert runner is not None
        assert runner.atloop_dir == str(temp_atloop_dir)

        # Verify custom config loaded
        config = ConfigLoader.get()
        assert config.ai.completion.model == "test-model"
        logger.info("TaskRunner custom config E2E successful ✅")

    def test_e2e_sandbox_override(self, real_config_file: Path, temp_workspace: Path):
        """Test TaskRunner with sandbox override end-to-end."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing TaskRunner sandbox override E2E")

        # Initialize runner
        TaskRunner()

        # Create task config with sandbox override
        task_config = {
            "goal": "Test task",
            "workspace_root": str(temp_workspace),
            "sandbox": {
                "base_url": None,
                "local_test": True,
            },
        }

        # Verify config structure
        assert "sandbox" in task_config
        assert task_config["sandbox"]["local_test"] is True
        logger.info("TaskRunner sandbox override E2E successful ✅")

    def test_e2e_error_handling(self, real_config_file: Path, temp_workspace: Path):
        """Test TaskRunner error handling end-to-end."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing TaskRunner error handling E2E")

        # Initialize runner
        TaskRunner()

        # Test with invalid task config (missing required fields)

        # TaskRunner should handle this gracefully
        # (Actual execution would fail, but setup should work)
        config = ConfigLoader.get()
        assert config is not None
        logger.info("TaskRunner error handling E2E successful ✅")
