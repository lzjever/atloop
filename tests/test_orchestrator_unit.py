"""Unit tests for orchestrator module."""

import logging
from pathlib import Path

from atloop.config.models import Budget
from atloop.orchestrator.budget import BudgetManager
from atloop.orchestrator.job_state import JobState
from atloop.orchestrator.state.manager import StateManager
from atloop.orchestrator.state_machine import Phase, StateMachine

logger = logging.getLogger(__name__)


class TestStateMachine:
    """Unit tests for StateMachine."""

    def test_initial_state(self):
        """Test initial state."""
        sm = StateMachine()
        assert sm.current_phase == Phase.DISCOVER
        assert not sm.is_terminal()

    def test_valid_transitions(self):
        """Test valid state transitions."""
        sm = StateMachine()

        # DISCOVER -> PLAN
        assert sm.transition(Phase.PLAN)
        assert sm.current_phase == Phase.PLAN

        # PLAN -> ACT
        assert sm.transition(Phase.ACT)
        assert sm.current_phase == Phase.ACT

        # ACT -> VERIFY
        assert sm.transition(Phase.VERIFY)
        assert sm.current_phase == Phase.VERIFY

        # VERIFY -> DONE
        assert sm.transition(Phase.DONE)
        assert sm.current_phase == Phase.DONE
        assert sm.is_terminal()

    def test_invalid_transitions(self):
        """Test invalid state transitions."""
        sm = StateMachine()

        # DISCOVER -> ACT (invalid)
        assert not sm.transition(Phase.ACT)
        assert sm.current_phase == Phase.DISCOVER

        # DISCOVER -> VERIFY (invalid)
        assert not sm.transition(Phase.VERIFY)
        assert sm.current_phase == Phase.DISCOVER

    def test_terminal_states(self):
        """Test terminal states."""
        sm = StateMachine()

        # Transition to DONE
        sm.transition(Phase.PLAN)
        sm.transition(Phase.ACT)
        sm.transition(Phase.VERIFY)
        sm.transition(Phase.DONE)
        assert sm.is_terminal()
        assert not sm.transition(Phase.DISCOVER)  # Can't transition from terminal

        # Transition to FAIL
        sm.reset()
        sm.transition(Phase.PLAN)
        sm.transition(Phase.FAIL)
        assert sm.is_terminal()

    def test_reset(self):
        """Test state machine reset."""
        sm = StateMachine()
        sm.transition(Phase.PLAN)
        sm.transition(Phase.ACT)
        sm.reset()
        assert sm.current_phase == Phase.DISCOVER
        assert not sm.is_terminal()


class TestBudgetManager:
    """Unit tests for BudgetManager."""

    def test_budget_manager_init(self):
        """Test BudgetManager initialization."""
        budget = Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600)
        manager = BudgetManager(budget)

        assert manager.budget.max_llm_calls == 10
        assert manager.budget.max_tool_calls == 50
        assert manager.budget.max_wall_time_sec == 3600

    def test_budget_manager_tracking(self):
        """Test budget tracking."""
        budget = Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600)
        manager = BudgetManager(budget)

        # Track LLM calls (directly update budget_used)
        manager.budget_used.llm_calls = 2
        assert manager.budget_used.llm_calls == 2

        # Track tool calls (directly update budget_used)
        manager.budget_used.tool_calls = 3
        assert manager.budget_used.tool_calls == 3

    def test_budget_manager_within_budget(self):
        """Test budget check - within budget."""
        budget = Budget(max_llm_calls=10, max_tool_calls=50, max_wall_time_sec=3600)
        manager = BudgetManager(budget)

        # Use some budget
        manager.budget_used.llm_calls = 5
        manager.budget_used.tool_calls = 20

        within_budget, msg = manager.check_all()
        assert within_budget is True

    def test_budget_manager_exhausted_llm(self):
        """Test budget check - LLM calls exhausted."""
        budget = Budget(max_llm_calls=5, max_tool_calls=50, max_wall_time_sec=3600)
        manager = BudgetManager(budget)

        # Exhaust LLM budget
        manager.budget_used.llm_calls = 6

        within_budget, msg = manager.check_llm_calls()
        assert within_budget is False
        assert msg is not None

    def test_budget_manager_exhausted_tools(self):
        """Test budget check - tool calls exhausted."""
        budget = Budget(max_llm_calls=10, max_tool_calls=5, max_wall_time_sec=3600)
        manager = BudgetManager(budget)

        # Exhaust tool budget
        manager.budget_used.tool_calls = 6

        within_budget, msg = manager.check_tool_calls()
        assert within_budget is False
        assert msg is not None


class TestStateManager:
    """Unit tests for StateManager."""

    def test_state_manager_init(self, temp_workspace: Path, temp_atloop_dir: Path):
        """Test StateManager initialization."""
        # Create state file path
        state_file = temp_atloop_dir / "agent_state.json"
        job_state = JobState(flow_id="test-flow")

        manager = StateManager(state_file, job_state)
        manager.load()

        assert manager.agent_state.step == 0
        assert manager.agent_state.phase == "DISCOVER"

    def test_state_manager_update(self, temp_workspace: Path, temp_atloop_dir: Path):
        """Test StateManager update."""
        # Create state file path
        state_file = temp_atloop_dir / "agent_state.json"
        job_state = JobState(flow_id="test-flow")

        manager = StateManager(state_file, job_state)
        manager.load()

        # Update step
        manager.update(step=5)
        assert manager.agent_state.step == 5

        # Update phase
        manager.update(phase="PLAN")
        assert manager.agent_state.phase == "PLAN"

        # Update both
        manager.update(step=10, phase="ACT")
        assert manager.agent_state.step == 10
        assert manager.agent_state.phase == "ACT"

    def test_state_manager_persistence(self, temp_workspace: Path, temp_atloop_dir: Path):
        """Test StateManager state persistence."""
        # Create state file path
        state_file = temp_atloop_dir / "agent_state.json"
        job_state = JobState(flow_id="test-flow")

        # Create first manager and update state
        manager1 = StateManager(state_file, job_state)
        manager1.load()
        manager1.update(step=5, phase="PLAN")
        manager1.save()

        # Create second manager (should load persisted state)
        job_state2 = JobState(flow_id="test-flow")
        manager2 = StateManager(state_file, job_state2)
        manager2.load()

        # State should be persisted
        assert manager2.agent_state.step == 5
        assert manager2.agent_state.phase == "PLAN"


class TestPhase:
    """Unit tests for Phase enum."""

    def test_phase_from_string(self):
        """Test Phase.from_string()."""
        assert Phase.from_string("DISCOVER") == Phase.DISCOVER
        assert Phase.from_string("PLAN") == Phase.PLAN
        assert Phase.from_string("ACT") == Phase.ACT
        assert Phase.from_string("VERIFY") == Phase.VERIFY
        assert Phase.from_string("DONE") == Phase.DONE
        assert Phase.from_string("FAIL") == Phase.FAIL

    def test_phase_value(self):
        """Test Phase.value."""
        assert Phase.DISCOVER.value == "DISCOVER"
        assert Phase.PLAN.value == "PLAN"
        assert Phase.ACT.value == "ACT"
        assert Phase.VERIFY.value == "VERIFY"
        assert Phase.DONE.value == "DONE"
        assert Phase.FAIL.value == "FAIL"
