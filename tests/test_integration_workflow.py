"""Integration tests for workflow phases and transitions."""

import logging
from pathlib import Path

import pytest

from atloop.config.loader import ConfigLoader
from atloop.config.models import Budget, TaskSpec
from atloop.orchestrator.coordinator import WorkflowCoordinator
from atloop.orchestrator.state_machine import Phase
from atloop.orchestrator.workflow.workflow import Workflow

pytestmark = pytest.mark.integration

logger = logging.getLogger(__name__)


class TestWorkflowPhaseTransitions:
    """Integration tests for workflow phase transitions."""

    def test_workflow_initial_phase(self, real_config_file: Path, temp_workspace: Path):
        """Test workflow starts in DISCOVER phase."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing workflow initial phase")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="test-workflow-001",
            goal="Test workflow phase transitions",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)
        Workflow(coordinator)

        # Check initial phase
        state = coordinator.state_manager.agent_state
        assert state.phase == "DISCOVER"
        assert coordinator.state_machine.current_phase == Phase.DISCOVER
        logger.info("Workflow starts in DISCOVER phase ✅")

    def test_workflow_phase_transition_discover_to_plan(
        self, real_config_file: Path, temp_workspace: Path
    ):
        """Test workflow transition from DISCOVER to PLAN."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing DISCOVER -> PLAN transition")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="test-workflow-002",
            goal="Test DISCOVER to PLAN transition",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Manually transition to PLAN
        coordinator.state_machine.transition(Phase.PLAN)
        coordinator.state_manager.update(phase="PLAN")

        # Verify transition
        assert coordinator.state_machine.current_phase == Phase.PLAN
        assert coordinator.state_manager.agent_state.phase == "PLAN"
        logger.info("DISCOVER -> PLAN transition successful ✅")

    def test_workflow_phase_transition_plan_to_act(
        self, real_config_file: Path, temp_workspace: Path
    ):
        """Test workflow transition from PLAN to ACT."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing PLAN -> ACT transition")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="test-workflow-003",
            goal="Test PLAN to ACT transition",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Transition to PLAN then ACT
        coordinator.state_machine.transition(Phase.PLAN)
        coordinator.state_manager.update(phase="PLAN")
        coordinator.state_machine.transition(Phase.ACT)
        coordinator.state_manager.update(phase="ACT")

        # Verify transition
        assert coordinator.state_machine.current_phase == Phase.ACT
        assert coordinator.state_manager.agent_state.phase == "ACT"
        logger.info("PLAN -> ACT transition successful ✅")

    def test_workflow_phase_transition_act_to_verify(
        self, real_config_file: Path, temp_workspace: Path
    ):
        """Test workflow transition from ACT to VERIFY."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing ACT -> VERIFY transition")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="test-workflow-004",
            goal="Test ACT to VERIFY transition",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Transition through phases
        coordinator.state_machine.transition(Phase.PLAN)
        coordinator.state_manager.update(phase="PLAN")
        coordinator.state_machine.transition(Phase.ACT)
        coordinator.state_manager.update(phase="ACT")
        coordinator.state_machine.transition(Phase.VERIFY)
        coordinator.state_manager.update(phase="VERIFY")

        # Verify transition
        assert coordinator.state_machine.current_phase == Phase.VERIFY
        assert coordinator.state_manager.agent_state.phase == "VERIFY"
        logger.info("ACT -> VERIFY transition successful ✅")

    def test_workflow_phase_transition_verify_to_discover(
        self, real_config_file: Path, temp_workspace: Path
    ):
        """Test workflow transition from VERIFY back to DISCOVER."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing VERIFY -> DISCOVER transition")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="test-workflow-005",
            goal="Test VERIFY to DISCOVER transition",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Transition through full cycle
        coordinator.state_machine.transition(Phase.PLAN)
        coordinator.state_manager.update(phase="PLAN")
        coordinator.state_machine.transition(Phase.ACT)
        coordinator.state_manager.update(phase="ACT")
        coordinator.state_machine.transition(Phase.VERIFY)
        coordinator.state_manager.update(phase="VERIFY")
        coordinator.state_machine.transition(Phase.DISCOVER)
        coordinator.state_manager.update(phase="DISCOVER")

        # Verify transition
        assert coordinator.state_machine.current_phase == Phase.DISCOVER
        assert coordinator.state_manager.agent_state.phase == "DISCOVER"
        logger.info("VERIFY -> DISCOVER transition successful ✅")


class TestWorkflowBudgetTracking:
    """Integration tests for budget tracking across workflow phases."""

    def test_workflow_budget_initialization(self, real_config_file: Path, temp_workspace: Path):
        """Test budget initialization in workflow."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing workflow budget initialization")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec with budget
        task_spec = TaskSpec(
            task_id="test-budget-001",
            goal="Test budget initialization",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Check budget manager
        assert coordinator.budget_manager is not None
        assert coordinator.budget_manager.budget.max_llm_calls == 10
        assert coordinator.budget_manager.budget.max_tool_calls == 50
        assert coordinator.budget_manager.budget.max_wall_time_sec == 3600

        # Check initial budget usage
        assert coordinator.budget_manager.budget_used.llm_calls == 0
        assert coordinator.budget_manager.budget_used.tool_calls == 0
        logger.info("Budget initialization successful ✅")

    def test_workflow_budget_tracking_llm_calls(self, real_config_file: Path, temp_workspace: Path):
        """Test budget tracking for LLM calls."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing budget tracking for LLM calls")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="test-budget-002",
            goal="Test LLM budget tracking",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Simulate LLM calls
        coordinator.budget_manager.budget_used.llm_calls = 3
        coordinator.state_manager.agent_state.budget_used.llm_calls = 3

        # Check budget
        within_budget, msg = coordinator.budget_manager.check_llm_calls()
        assert within_budget is True
        assert coordinator.budget_manager.budget_used.llm_calls == 3
        logger.info("LLM budget tracking successful ✅")

    def test_workflow_budget_tracking_tool_calls(
        self, real_config_file: Path, temp_workspace: Path
    ):
        """Test budget tracking for tool calls."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing budget tracking for tool calls")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec
        task_spec = TaskSpec(
            task_id="test-budget-003",
            goal="Test tool budget tracking",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Simulate tool calls
        coordinator.budget_manager.budget_used.tool_calls = 20
        coordinator.state_manager.agent_state.budget_used.tool_calls = 20

        # Check budget
        within_budget, msg = coordinator.budget_manager.check_tool_calls()
        assert within_budget is True
        assert coordinator.budget_manager.budget_used.tool_calls == 20
        logger.info("Tool budget tracking successful ✅")

    def test_workflow_budget_exhaustion(self, real_config_file: Path, temp_workspace: Path):
        """Test budget exhaustion detection."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing budget exhaustion detection")

        # Setup config
        ConfigLoader.setup()
        config = ConfigLoader.get()

        # Create task spec with small budget
        task_spec = TaskSpec(
            task_id="test-budget-004",
            goal="Test budget exhaustion",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=5, max_tool_calls=10, max_wall_time_sec=3600),
        )

        # Initialize coordinator
        coordinator = WorkflowCoordinator(task_spec, config)

        # Exhaust LLM budget
        coordinator.budget_manager.budget_used.llm_calls = 6
        within_budget, msg = coordinator.budget_manager.check_llm_calls()
        assert within_budget is False
        assert msg is not None
        logger.info("Budget exhaustion detection successful ✅")


class TestWorkflowStatePersistence:
    """Integration tests for state persistence across workflow phases."""

    def test_workflow_state_persistence(
        self, real_config_file: Path, temp_workspace: Path, temp_atloop_dir: Path
    ):
        """Test state persistence across phases."""
        if not real_config_file.exists():
            pytest.skip(f"Real config file not found: {real_config_file}")

        logger.info("Testing workflow state persistence")

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
            task_id="test-persistence-001",
            goal="Test state persistence",
            workspace_root=str(temp_workspace),
            budget=Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600),
        )

        # Initialize first coordinator
        coordinator1 = WorkflowCoordinator(task_spec, config)
        coordinator1.state_manager.update(step=5, phase="PLAN")
        coordinator1.state_manager.save()

        # Initialize second coordinator (should load persisted state)
        coordinator2 = WorkflowCoordinator(task_spec, config)

        # Verify state persistence
        assert coordinator2.state_manager.agent_state.step == 5
        assert coordinator2.state_manager.agent_state.phase == "PLAN"
        logger.info("State persistence successful ✅")
