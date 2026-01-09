"""Integration tests for workflow components using real configuration."""

import logging
from pathlib import Path

import pytest

from atloop.config.loader import ConfigLoader
from atloop.config.models import Budget, TaskSpec

pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)


class TestWorkflowIntegration:
    """Integration tests for workflow with real config."""

    def test_task_spec_creation(self, real_config_file: Path, temp_workspace: Path):
        """Test TaskSpec creation with real config."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing TaskSpec creation")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="test-task-123",
            goal="Test task goal",
            workspace_root=str(temp_workspace),
            constraints=[],
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
            task_type="bugfix",
        )

        assert task_spec is not None
        assert task_spec.task_id == "test-task-123"
        assert task_spec.goal == "Test task goal"
        assert task_spec.workspace_root == str(temp_workspace)
        assert config is not None
        logger.info("TaskSpec created successfully")

    def test_budget_creation(self, real_config_file: Path):
        """Test Budget creation with real config."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing Budget creation")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create budget
        budget = Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600)
        assert budget is not None
        assert budget.max_llm_calls == 10
        assert budget.max_tool_calls == 50
        assert budget.max_wall_time_sec == 3600
        assert config.default_budget is not None
        logger.info("Budget created successfully")
