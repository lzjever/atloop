"""Validation tests for configuration."""

import logging
from pathlib import Path

import pytest

from atloop.config.loader import ConfigLoader
from atloop.config.models import AtloopConfig

logger = logging.getLogger(__name__)


class TestConfigValidation:
    """Validation tests for configuration."""

    def test_validation_real_config(self, real_config_file: Path):
        """Test real config validation."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing real config validation")

        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Validate structure
        assert isinstance(config, AtloopConfig)
        assert config.ai is not None
        assert config.ai.completion is not None
        assert config.ai.performance is not None
        assert config.sandbox is not None
        assert config.default_budget is not None
        assert config.memory is not None

        logger.info("Real config validation successful ✅")

    def test_validation_config_structure(self, real_config_file: Path):
        """Test config structure validation."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing config structure validation")

        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Validate nested structure
        assert hasattr(config, "ai")
        assert hasattr(config.ai, "completion")
        assert hasattr(config.ai, "performance")
        assert hasattr(config, "sandbox")
        assert hasattr(config, "default_budget")
        assert hasattr(config, "memory")

        # Validate required fields
        assert config.ai.completion.model is not None
        assert config.ai.completion.api_base is not None
        assert config.ai.performance.max_tokens_input > 0
        assert config.ai.performance.max_tokens_output > 0

        logger.info("Config structure validation successful ✅")

    def test_validation_config_types(self, real_config_file: Path):
        """Test config type validation."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing config type validation")

        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Type validation (varlord ensures types are correct)
        assert isinstance(config.ai.completion.model, str)
        assert isinstance(config.ai.completion.api_base, str)
        assert isinstance(config.ai.performance.max_tokens_input, int)
        assert isinstance(config.ai.performance.max_tokens_output, int)
        assert isinstance(config.default_budget.max_llm_calls, int)
        assert isinstance(config.default_budget.max_tool_calls, int)

        logger.info("Config type validation successful ✅")

    def test_validation_config_required_fields(self, real_config_file: Path):
        """Test required fields validation."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing required fields validation")

        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Required fields should be present
        assert config.ai.completion.model is not None
        assert config.ai.completion.api_base is not None
        # API key might be None in some cases, but model and api_base are required

        logger.info("Required fields validation successful ✅")

    def test_validation_config_ranges(self, real_config_file: Path):
        """Test config value ranges."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing config value ranges")

        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Validate ranges
        assert config.ai.performance.max_tokens_input > 0
        assert config.ai.performance.max_tokens_output > 0
        assert config.default_budget.max_llm_calls > 0
        assert config.default_budget.max_tool_calls > 0
        assert config.default_budget.max_wall_time_sec > 0

        logger.info("Config value ranges validation successful ✅")

    def test_validation_config_env_overrides(self, real_config_file: Path, temp_atloop_dir: Path):
        """Test environment variable overrides."""
        import os

        logger.info("Testing environment variable overrides")

        # Create minimal config
        config_file = temp_atloop_dir / "config" / "atloop.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("""
ai:
  completion:
    model: file-model
    api_base: https://file.api.com
    api_key: file-key
  performance:
    max_tokens_input: 1000
    max_tokens_output: 500
sandbox:
  base_url: http://file:8080
  local_test: true
default_budget:
  max_llm_calls: 10
  max_tool_calls: 50
  max_wall_time_sec: 3600
""")

        # Set environment variable
        os.environ["ATLOOP__AI__COMPLETION__MODEL"] = "env-model"

        try:
            ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))
            config = ConfigLoader.get()

            # Environment variable should override file config
            assert config.ai.completion.model == "env-model"
            logger.info("Environment variable overrides validation successful ✅")
        finally:
            # Clean up
            os.environ.pop("ATLOOP__AI__COMPLETION__MODEL", None)
