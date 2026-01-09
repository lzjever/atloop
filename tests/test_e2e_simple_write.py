"""E2E test for simple write file scenario - tests basic tool execution."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from atloop.config.loader import ConfigLoader
from atloop.config.models import Budget, TaskSpec
from atloop.orchestrator.coordinator import WorkflowCoordinator

pytestmark = pytest.mark.e2e

logger = logging.getLogger(__name__)


class TestE2ESimpleWrite:
    """E2E test for simple write file scenario."""

    def test_e2e_simple_write_setup(self, real_config_file: Path, temp_workspace: Path):
        """Test E2E simple write file scenario setup."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing E2E simple write file scenario")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-simple-write",
            goal="Write some arbitrary Python code to a file",
            workspace_root=str(temp_workspace),
            task_type="feature",
            constraints=[],
            budget=Budget(max_llm_calls=10, max_tool_calls=20, max_wall_time_sec=600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        assert coordinator is not None
        assert coordinator.task_spec.task_id == "e2e-simple-write"
        assert coordinator.state_manager.agent_state.phase == "DISCOVER"
        assert coordinator.tool_runtime is not None
        assert coordinator.tool_runtime.registry is not None

        logger.info("Simple write scenario setup successful ✅")

    def test_e2e_simple_write_tool_execution(self, real_config_file: Path, temp_workspace: Path):
        """Test tool execution in simple write scenario."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing tool execution in simple write scenario")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-simple-write-exec",
            goal="Write some arbitrary Python code",
            workspace_root=str(temp_workspace),
            task_type="feature",
            constraints=[],
            budget=Budget(max_llm_calls=10, max_tool_calls=20, max_wall_time_sec=600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Test tool execution via registry
        from atloop.orchestrator.executor.tool_executor import ToolExecutor

        executor = ToolExecutor(coordinator)

        # Test write_file tool execution
        action = {
            "tool": "write_file",
            "args": {
                "path": "test_file.py",
                "content": "print('Hello, World!')",
            },
        }

        try:
            result = executor._execute_action(action)
            logger.info(f"Tool execution result: success={result.get('success')}")
            assert "success" in result
            assert result.get("tool") == "write_file"
            logger.info("Tool execution test successful ✅")
        except AttributeError as e:
            if "execute_tool" in str(e):
                pytest.fail(
                    f"ToolRuntime.execute_tool() does not exist. Use registry.execute() instead. Error: {e}"
                )
            raise
        except Exception as e:
            # If sandbox is not available, that's okay for this test
            if "Connection" in str(e) or "sandbox" in str(e).lower():
                logger.warning(f"Sandbox not available, skipping execution test: {e}")
                pytest.skip(f"Sandbox not available: {e}")
            else:
                raise

    def test_e2e_simple_write_full_workflow(self, real_config_file: Path, temp_workspace: Path):
        """Test full workflow for simple write scenario (mocked)."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing full workflow for simple write scenario")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="e2e-simple-write-full",
            goal="Write some arbitrary Python code",
            workspace_root=str(temp_workspace),
            task_type="feature",
            constraints=[],
            budget=Budget(max_llm_calls=5, max_tool_calls=10, max_wall_time_sec=300),
        )

        # Mock sandbox to avoid actual execution
        with patch("atloop.runtime.sandbox_adapter.SandboxAdapter") as mock_sandbox:
            mock_sandbox_instance = MagicMock()
            mock_sandbox.return_value = mock_sandbox_instance

            # Initialize coordinator with mocked sandbox
            coordinator = WorkflowCoordinator(task_spec, config)

            # Verify coordinator is set up correctly
            assert coordinator is not None
            assert coordinator.tool_runtime is not None
            assert coordinator.tool_runtime.registry is not None

            # Test that we can access registry.execute
            assert hasattr(coordinator.tool_runtime.registry, "execute")

            logger.info("Full workflow setup test successful ✅")
