"""Test event definitions."""

import pytest
from datetime import datetime
from atloop.output.events import (
    EventType,
    OutputEvent,
    TaskStartEvent,
    PhaseTransitionEvent,
    ToolCallEvent,
    ToolResultEvent,
    LLMCallEvent,
    LLMStreamEvent,
    LLMResultEvent,
    BudgetUpdateEvent,
    TaskCompleteEvent,
    ErrorEvent,
)


class TestEventImmutability:
    """Test that all events are immutable."""

    def test_task_start_event_immutable(self):
        """Test TaskStartEvent is immutable."""
        event = TaskStartEvent(
            step=1,
            task_id="test",
            goal="test",
            workspace_root="/tmp",
            model="test",
            budget={"max_llm_calls": 50},
        )
        with pytest.raises(Exception):  # Should raise FrozenInstanceError or similar
            event.step = 2

    def test_phase_transition_event_immutable(self):
        """Test PhaseTransitionEvent is immutable."""
        event = PhaseTransitionEvent(
            step=1,
            task_id="test",
            phase="DISCOVER",
        )
        with pytest.raises(Exception):
            event.phase = "PLAN"

    def test_tool_call_event_immutable(self):
        """Test ToolCallEvent is immutable."""
        event = ToolCallEvent(
            step=1,
            task_id="test",
            tool_name="run",
            tool_args={"cmd": "echo test"},
        )
        with pytest.raises(Exception):
            event.tool_name = "write_file"


class TestEventCreation:
    """Test event creation with required fields."""

    def test_task_start_event_creation(self):
        """Test TaskStartEvent creation."""
        event = TaskStartEvent(
            step=1,
            task_id="test",
            goal="Fix bug",
            workspace_root="/tmp",
            model="deepseek-chat",
            budget={"max_llm_calls": 50, "max_tool_calls": 100},
        )
        assert event.event_type == EventType.TASK_START
        assert event.step == 1
        assert event.task_id == "test"
        assert event.goal == "Fix bug"
        assert isinstance(event.timestamp, datetime)

    def test_phase_transition_event_creation(self):
        """Test PhaseTransitionEvent creation."""
        event = PhaseTransitionEvent(
            step=2,
            task_id="test",
            phase="PLAN",
            previous_phase="DISCOVER",
        )
        assert event.event_type == EventType.PHASE_TRANSITION
        assert event.phase == "PLAN"
        assert event.previous_phase == "DISCOVER"

    def test_tool_result_event_creation(self):
        """Test ToolResultEvent creation."""
        event = ToolResultEvent(
            step=3,
            task_id="test",
            tool_name="run",
            success=True,
            stdout="output",
            exit_code=0,
        )
        assert event.event_type == EventType.TOOL_RESULT
        assert event.success is True
        assert event.stdout == "output"
        assert event.exit_code == 0

    def test_llm_result_event_creation(self):
        """Test LLMResultEvent creation."""
        event = LLMResultEvent(
            step=2,
            task_id="test",
            model="deepseek-chat",
            tokens_in=100,
            tokens_out=50,
            actions=[{"tool": "run", "args": {"cmd": "test"}}],
            stop_reason="continue",
            duration_ms=1000,
        )
        assert event.event_type == EventType.LLM_RESULT
        assert event.tokens_in == 100
        assert event.tokens_out == 50
        assert len(event.actions) == 1

    def test_budget_update_event_creation(self):
        """Test BudgetUpdateEvent creation."""
        event = BudgetUpdateEvent(
            step=5,
            task_id="test",
            llm_calls_used=10,
            llm_calls_max=50,
            tool_calls_used=5,
            tool_calls_max=100,
            wall_time_sec_used=30,
            wall_time_sec_max=300,
        )
        assert event.event_type == EventType.BUDGET_UPDATE
        assert event.llm_calls_used == 10
        assert event.llm_calls_max == 50

    def test_task_complete_event_creation(self):
        """Test TaskCompleteEvent creation."""
        event = TaskCompleteEvent(
            step=10,
            task_id="test",
            status="success",
            final_step=10,
            duration_sec=120,
            budget_used={"llm_calls": 12, "tool_calls": 8},
        )
        assert event.event_type == EventType.TASK_COMPLETE
        assert event.status == "success"
        assert event.final_step == 10

    def test_error_event_creation(self):
        """Test ErrorEvent creation."""
        event = ErrorEvent(
            step=5,
            task_id="test",
            phase="ACT",
            error_type="ValueError",
            error_message="Test error",
            recoverable=True,
        )
        assert event.event_type == EventType.ERROR
        assert event.phase == "ACT"
        assert event.error_type == "ValueError"
        assert event.recoverable is True


class TestEventDefaults:
    """Test event default values."""

    def test_output_event_defaults(self):
        """Test OutputEvent has correct defaults."""
        # OutputEvent is abstract, test via subclass
        event = TaskStartEvent(
            step=0,
            task_id="",
            goal="",
            workspace_root="",
            model="",
        )
        assert event.event_type == EventType.TASK_START
        assert isinstance(event.timestamp, datetime)
        assert event.budget == {}
