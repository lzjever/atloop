"""Unit tests for configuration module."""

import logging
import os
from pathlib import Path

import pytest

from atloop.config.loader import ConfigLoader
from atloop.config.models import (
    AtloopConfig,
    Budget,
    MemoryConfig,
    SandboxConfig,
    TaskSpec,
)

logger = logging.getLogger(__name__)


class TestConfigLoader:
    """Unit tests for ConfigLoader."""

    def test_config_loader_setup_default(self, temp_atloop_dir: Path):
        """Test ConfigLoader.setup() with default directory."""
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

        ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))
        config = ConfigLoader.get()

        assert config is not None
        assert isinstance(config, AtloopConfig)
        assert config.ai.completion.model == "test-model"

    def test_config_loader_get_returns_valid_config(self, real_config_file: Path):
        """Test ConfigLoader.get() returns valid config."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        ConfigLoader.setup()
        config = ConfigLoader.get()

        assert config is not None
        assert isinstance(config, AtloopConfig)
        assert config.ai is not None
        assert config.ai.completion is not None

    def test_config_loader_custom_dir(self, temp_atloop_dir: Path):
        """Test ConfigLoader with custom atloop directory."""
        config_file = temp_atloop_dir / "config" / "atloop.yaml"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("""
ai:
  completion:
    model: custom-model
    api_base: https://custom.api.com
    api_key: custom-key
  performance:
    max_tokens_input: 2000
    max_tokens_output: 1000
sandbox:
  base_url: http://custom:8080
  local_test: false
default_budget:
  max_llm_calls: 20
  max_tool_calls: 100
  max_wall_time_sec: 7200
""")

        ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))
        config = ConfigLoader.get()

        assert config.ai.completion.model == "custom-model"
        assert config.ai.completion.api_base == "https://custom.api.com"
        assert config.sandbox.local_test is False

    def test_config_loader_env_override(self, temp_atloop_dir: Path):
        """Test ConfigLoader with environment variable overrides."""
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
        finally:
            # Clean up
            os.environ.pop("ATLOOP__AI__COMPLETION__MODEL", None)


class TestAtloopConfig:
    """Unit tests for AtloopConfig model."""

    def test_atloop_config_validation(self, temp_atloop_dir: Path):
        """Test AtloopConfig model validation."""
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

        ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))
        config = ConfigLoader.get()

        # Validate structure
        assert config.ai is not None
        assert config.ai.completion is not None
        assert config.ai.performance is not None
        assert config.sandbox is not None
        assert config.default_budget is not None
        assert config.memory is not None

    def test_atloop_config_type_safety(self, temp_atloop_dir: Path):
        """Test AtloopConfig type safety (varlord validation)."""
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

        ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))
        config = ConfigLoader.get()

        # Type safety: config should be AtloopConfig instance
        assert isinstance(config, AtloopConfig)
        assert isinstance(config.ai.completion.model, str)
        assert isinstance(config.default_budget.max_llm_calls, int)


class TestTaskSpec:
    """Unit tests for TaskSpec model."""

    def test_task_spec_creation(self, temp_workspace: Path):
        """Test TaskSpec creation."""
        task_spec = TaskSpec(
            task_id="test-task-123",
            goal="Test task goal",
            workspace_root=str(temp_workspace),
            constraints=["constraint1", "constraint2"],
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
            task_type="bugfix",
        )

        assert task_spec.task_id == "test-task-123"
        assert task_spec.goal == "Test task goal"
        assert task_spec.workspace_root == str(temp_workspace)
        assert len(task_spec.constraints) == 2
        assert task_spec.task_type == "bugfix"

    def test_task_spec_validation(self, temp_workspace: Path):
        """Test TaskSpec validation."""
        # Valid task spec
        task_spec = TaskSpec(
            task_id="test-task",
            goal="Test goal",
            workspace_root=str(temp_workspace),
        )
        assert task_spec is not None

        # Invalid task type should raise ValueError
        with pytest.raises(ValueError):
            TaskSpec(
                task_id="test-task",
                goal="Test goal",
                workspace_root=str(temp_workspace),
                task_type="invalid",
            )

    def test_task_spec_defaults(self, temp_workspace: Path):
        """Test TaskSpec default values."""
        task_spec = TaskSpec(
            task_id="test-task",
            goal="Test goal",
            workspace_root=str(temp_workspace),
        )

        assert task_spec.constraints == []
        assert task_spec.task_type == "bugfix"
        assert task_spec.budget is not None


class TestBudget:
    """Unit tests for Budget model."""

    def test_budget_creation(self):
        """Test Budget creation."""
        budget = Budget(
            max_llm_calls=10,
            max_tool_calls=50,
            max_wall_time_sec=3600,
        )

        assert budget.max_llm_calls == 10
        assert budget.max_tool_calls == 50
        assert budget.max_wall_time_sec == 3600

    def test_budget_defaults(self):
        """Test Budget default values."""
        budget = Budget()

        # Budget has default values from model
        assert budget.max_llm_calls >= 0
        assert budget.max_tool_calls >= 0
        assert budget.max_wall_time_sec >= 0


class TestSandboxConfig:
    """Unit tests for SandboxConfig model."""

    def test_sandbox_config_creation(self):
        """Test SandboxConfig creation."""
        sandbox_config = SandboxConfig(
            base_url="http://test:8080",
            local_test=True,
        )

        assert sandbox_config.base_url == "http://test:8080"
        assert sandbox_config.local_test is True

    def test_sandbox_config_defaults(self):
        """Test SandboxConfig default values."""
        # SandboxConfig requires base_url or local_test=True
        sandbox_config = SandboxConfig(local_test=True)

        assert sandbox_config.base_url is None
        assert sandbox_config.local_test is True


class TestMemoryConfig:
    """Unit tests for MemoryConfig model."""

    def test_memory_config_creation(self):
        """Test MemoryConfig creation."""
        memory_config = MemoryConfig(
            summary_max_length=96000,
            summary_min_effective_length=24000,
            compression_threshold=80000,
            compression_target=60000,
        )

        assert memory_config.summary_max_length == 96000
        assert memory_config.summary_min_effective_length == 24000
        assert memory_config.compression_threshold == 80000
        assert memory_config.compression_target == 60000
