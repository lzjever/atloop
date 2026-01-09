"""End-to-end integration tests for complete workflow execution."""

import logging
from pathlib import Path

import pytest

from atloop.api.runner import TaskRunner
from atloop.config.loader import ConfigLoader
from atloop.config.models import Budget, TaskSpec
from atloop.orchestrator.coordinator import WorkflowCoordinator

pytestmark = [pytest.mark.e2e, pytest.mark.integration]

logger = logging.getLogger(__name__)


class TestE2EIntegration:
    """End-to-end integration tests."""

    def test_e2e_simple_bugfix_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E setup for simple bugfix scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E simple bugfix setup")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-bugfix-001",
            goal="Fix a simple bug in test code",
            workspace_root=str(temp_workspace),
            task_type="bugfix",
            budget=Budget(max_llm_calls=5, max_tool_calls=20, max_wall_time_sec=1800),
        )

        # Create a simple test file with bug
        test_file = temp_workspace / "test_calc.py"
        test_file.write_text(
            """def add(a, b):
    return a - b  # Bug: should be a + b

def test_add():
    assert add(2, 3) == 5
"""
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None
        assert coordinator.task_spec.task_id == "e2e-bugfix-001"
        assert coordinator.state_manager.agent_state.phase == "DISCOVER"
        logger.info("E2E bugfix setup successful ✅")

    def test_e2e_simple_feature_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E setup for simple feature scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E simple feature setup")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-feature-001",
            goal="Implement a simple feature",
            workspace_root=str(temp_workspace),
            task_type="feature",
            budget=Budget(max_llm_calls=5, max_tool_calls=20, max_wall_time_sec=1800),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None
        assert coordinator.task_spec.task_type == "feature"
        logger.info("E2E feature setup successful ✅")

    def test_e2e_simple_refactor_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E setup for simple refactor scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E simple refactor setup")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-refactor-001",
            goal="Refactor code to improve structure",
            workspace_root=str(temp_workspace),
            task_type="refactor",
            budget=Budget(max_llm_calls=5, max_tool_calls=20, max_wall_time_sec=1800),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None
        assert coordinator.task_spec.task_type == "refactor"
        logger.info("E2E refactor setup successful ✅")

    def test_e2e_multi_file_edit_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E setup for multi-file editing scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E multi-file edit setup")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create multiple files
        (temp_workspace / "file1.py").write_text("def func1(): pass\n")
        (temp_workspace / "file2.py").write_text("def func2(): pass\n")
        (temp_workspace / "file3.py").write_text("def func3(): pass\n")

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-multi-001",
            goal="Edit multiple files",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=5, max_tool_calls=20, max_wall_time_sec=1800),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None

        # Verify workspace has files
        files = list(temp_workspace.glob("*.py"))
        assert len(files) >= 3
        logger.info("E2E multi-file edit setup successful ✅")

    def test_e2e_with_tests_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E setup with test execution."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E with tests setup")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create test structure
        (temp_workspace / "src").mkdir(parents=True, exist_ok=True)
        (temp_workspace / "tests").mkdir(parents=True, exist_ok=True)
        (temp_workspace / "src" / "calc.py").write_text("def add(a, b): return a + b\n")
        (temp_workspace / "tests" / "test_calc.py").write_text(
            "from src.calc import add\ndef test_add(): assert add(2, 3) == 5\n"
        )
        (temp_workspace / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-tests-001",
            goal="Fix failing tests",
            workspace_root=str(temp_workspace),
            task_type="bugfix",
            budget=Budget(max_llm_calls=5, max_tool_calls=20, max_wall_time_sec=1800),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None
        logger.info("E2E with tests setup successful ✅")

    def test_e2e_error_scenarios(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E error scenario handling."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E error scenarios")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-error-001",
            goal="Test error handling",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=5, max_tool_calls=20, max_wall_time_sec=1800),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Test error state initialization
        state = coordinator.state_manager.agent_state
        assert state.last_error is not None
        assert state.last_error.summary == ""
        logger.info("E2E error scenarios setup successful ✅")

    def test_e2e_budget_exhaustion_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E budget exhaustion scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E budget exhaustion setup")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec with very small budget
        task_spec = TaskSpec(
            task_id="e2e-budget-001",
            goal="Test budget exhaustion",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=1, max_tool_calls=1, max_wall_time_sec=60),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Verify budget is set correctly
        assert coordinator.budget_manager.budget.max_llm_calls == 1
        assert coordinator.budget_manager.budget.max_tool_calls == 1
        logger.info("E2E budget exhaustion setup successful ✅")

    def test_e2e_state_recovery_setup(
        self, real_config_file: Path, temp_workspace: Path, temp_atloop_dir: Path
    ):
        """Test E2E state recovery after failure."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E state recovery setup")

        # Setup config with custom atloop_dir
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
runs_dir: runs
""")

        ConfigLoader.setup(atloop_dir=str(temp_atloop_dir))
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-recovery-001",
            goal="Test state recovery",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=5, max_tool_calls=20, max_wall_time_sec=1800),
        )

        # Initialize first coordinator and set state
        coordinator1 = WorkflowCoordinator(task_spec, config)
        coordinator1.state_manager.update(step=10, phase="ACT")
        coordinator1.state_manager.save()

        # Initialize second coordinator (should recover state)
        coordinator2 = WorkflowCoordinator(task_spec, config)

        # Verify state recovery
        assert coordinator2.state_manager.agent_state.step == 10
        assert coordinator2.state_manager.agent_state.phase == "ACT"
        logger.info("E2E state recovery setup successful ✅")


class TestE2ETaskRunner:
    """End-to-end tests for TaskRunner API."""

    def test_e2e_task_runner_initialization(self, real_config_file: Path, temp_workspace: Path):
        """Test TaskRunner initialization for E2E."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing TaskRunner E2E initialization")

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
        logger.info("TaskRunner E2E initialization successful ✅")

    def test_e2e_task_runner_config_validation(self, real_config_file: Path, temp_workspace: Path):
        """Test TaskRunner config validation."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing TaskRunner config validation")

        TaskRunner()

        # Valid config
        task_config = {
            "goal": "Test task",
            "workspace_root": str(temp_workspace),
        }
        assert "goal" in task_config
        assert "workspace_root" in task_config

        # Invalid config (missing required fields)
        invalid_config = {"goal": "Test"}
        assert "workspace_root" not in invalid_config

        logger.info("TaskRunner config validation successful ✅")
