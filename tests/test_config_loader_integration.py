"""Integration tests for ConfigLoader using real configuration."""

import logging
from pathlib import Path

import pytest

from atloop.config.loader import ConfigLoader
from atloop.config.models import AtloopConfig

pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)


class TestConfigLoaderIntegration:
    """Integration tests for ConfigLoader with real config."""

    def test_load_real_config(self, real_config_file: Path):
        """Test loading real configuration from user's home directory."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info(f"Testing with real config: {real_config_file}")

        # Setup config loader
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Verify config is loaded
        assert config is not None
        assert isinstance(config, AtloopConfig)

        # Verify AI config
        assert config.ai is not None
        assert config.ai.completion is not None
        assert config.ai.completion.model is not None
        assert config.ai.completion.api_base is not None
        logger.info(f"AI Model: {config.ai.completion.model}")
        logger.info(f"AI API Base: {config.ai.completion.api_base}")

        # Verify performance config
        assert config.ai.performance is not None
        assert config.ai.performance.max_tokens_input > 0
        assert config.ai.performance.max_tokens_output > 0
        logger.info(f"Max Tokens Input: {config.ai.performance.max_tokens_input}")
        logger.info(f"Max Tokens Output: {config.ai.performance.max_tokens_output}")

        # Verify sandbox config
        assert config.sandbox is not None
        logger.info(f"Sandbox Base URL: {config.sandbox.base_url}")
        logger.info(f"Sandbox Local Test: {config.sandbox.local_test}")

        # Verify default budget
        assert config.default_budget is not None
        assert config.default_budget.max_llm_calls > 0
        assert config.default_budget.max_tool_calls > 0
        assert config.default_budget.max_wall_time_sec > 0
        logger.info(
            f"Default Budget: LLM={config.default_budget.max_llm_calls}, "
            f"Tools={config.default_budget.max_tool_calls}, "
            f"Time={config.default_budget.max_wall_time_sec}s"
        )

        # Verify memory config
        assert config.memory is not None
        logger.info(f"Memory Summary Max Length: {config.memory.summary_max_length}")

    def test_config_loader_singleton(self, real_config_file: Path):
        """Test that ConfigLoader returns same config values."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        # Setup config
        ConfigLoader.setup()
        config1 = ConfigLoader.get()
        config2 = ConfigLoader.get()

        # Should return same config values (varlord load() returns new instance but same values)
        assert config1.ai.completion.model == config2.ai.completion.model
        assert config1.ai.completion.api_base == config2.ai.completion.api_base
        assert config1.default_budget.max_llm_calls == config2.default_budget.max_llm_calls

    def test_config_loader_with_custom_dir(self, temp_atloop_dir: Path):
        """Test ConfigLoader with custom atloop directory."""
        # Create a minimal config file
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

        # Setup with custom dir
        ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))
        config = ConfigLoader.get()

        # Verify custom config loaded
        assert config.ai.completion.model == "test-model"
        assert config.ai.completion.api_base == "https://test.api.com"
        assert config.sandbox.local_test is True
        assert config.default_budget.max_llm_calls == 10
