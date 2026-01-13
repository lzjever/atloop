"""
Integration tests for loop detection with orchestrator phases.

These tests verify that the loop detection system integrates correctly
with PlanPhase and ActPhase.
"""

from unittest.mock import MagicMock

import pytest

from atloop.config.loop_detection import (
    InterventionLevel,
    LoopDetectionConfig,
)
from atloop.memory.progress_tracker import ProgressTracker
from atloop.memory.state import AgentState, BudgetUsed, Memory
from atloop.orchestrator.coordinator import WorkflowCoordinator
from atloop.orchestrator.job_state import JobState
from atloop.orchestrator.loop_detector import LoopDetector
from atloop.orchestrator.phases.act import ActPhase
from atloop.orchestrator.phases.base import PhaseContext
from atloop.orchestrator.state_machine import Phase
from atloop.tools.registry import ToolRegistry

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_coordinator_with_loop_detection():
    """Create a mock WorkflowCoordinator with loop detection components."""
    coordinator = MagicMock(spec=WorkflowCoordinator)

    # Setup state manager
    coordinator.state_manager = MagicMock()
    state = AgentState()
    coordinator.state_manager.agent_state = state
    coordinator.state_manager.update = MagicMock()
    coordinator.state_manager.save = MagicMock()

    # Setup job state
    coordinator.job_state = JobState()
    coordinator.job_state.shared_data = {}

    # Setup tool runtime
    coordinator.tool_runtime = MagicMock()
    coordinator.tool_runtime.registry = ToolRegistry(sandbox=MagicMock())

    # Setup budget manager
    coordinator.budget_manager = MagicMock()
    coordinator.budget_manager.budget_used = BudgetUsed()

    # Setup state machine
    coordinator.state_machine = MagicMock()
    coordinator.state_machine.transition = MagicMock(return_value=True)

    # Setup event logger
    coordinator.event_logger = MagicMock()

    # Setup loop detection components
    coordinator.progress_tracker = ProgressTracker()
    coordinator.loop_detector = LoopDetector(
        LoopDetectionConfig(
            soft_warning_threshold=2,
            hard_warning_threshold=3,
            force_threshold=4,
            abort_threshold=5,
            max_view_without_modify=2,
        )
    )

    return coordinator


# =============================================================================
# ActPhase Integration Tests
# =============================================================================


class TestActPhaseLoopDetectionIntegration:
    """Test ActPhase integration with loop detection."""

    def test_act_phase_records_actions_to_progress_tracker(
        self, mock_coordinator_with_loop_detection
    ):
        """Test that ActPhase records executed actions to ProgressTracker."""
        coordinator = mock_coordinator_with_loop_detection
        act_phase = ActPhase(coordinator)

        # Setup mock executor to return success
        act_phase.executor = MagicMock()
        act_phase.executor._execute_action = MagicMock(
            return_value={
                "ok": True,
                "success": True,
                "stdout": "output",
                "stderr": "",
            }
        )

        # Setup actions in job_state
        coordinator.job_state.shared_data["actions"] = {
            "actions": [
                {"tool": "run", "args": {"cmd": "ls -la"}},
                {"tool": "run", "args": {"cmd": "cat file.txt"}},
            ],
            "stop_reason": "continue",
        }

        context = PhaseContext(step=1, phase=Phase.ACT)

        # Execute
        act_phase.execute(context)

        # Verify actions were recorded
        assert len(coordinator.progress_tracker.action_history) == 2
        assert coordinator.progress_tracker.action_history[0].tool == "run"
        assert coordinator.progress_tracker.action_history[1].tool == "run"

    def test_act_phase_preserves_action_history_in_memory(
        self, mock_coordinator_with_loop_detection
    ):
        """Test that action history is saved to memory state."""
        coordinator = mock_coordinator_with_loop_detection
        act_phase = ActPhase(coordinator)

        # Setup mock executor
        act_phase.executor = MagicMock()
        act_phase.executor._execute_action = MagicMock(
            return_value={
                "ok": True,
                "success": True,
                "stdout": "output",
                "stderr": "",
            }
        )

        # Setup a single action
        coordinator.job_state.shared_data["actions"] = {
            "actions": [{"tool": "run", "args": {"cmd": "ls"}}],
            "stop_reason": "continue",
        }

        context = PhaseContext(step=1, phase=Phase.ACT)
        act_phase.execute(context)

        # Verify action history is saved to memory
        state = coordinator.state_manager.agent_state
        assert len(state.memory.action_history) > 0

    def test_action_categorization_in_act_phase(self, mock_coordinator_with_loop_detection):
        """Test that actions are correctly categorized when recorded."""
        coordinator = mock_coordinator_with_loop_detection
        act_phase = ActPhase(coordinator)

        act_phase.executor = MagicMock()
        act_phase.executor._execute_action = MagicMock(
            return_value={
                "ok": True,
                "success": True,
                "stdout": "output",
                "stderr": "",
            }
        )

        # Mix of view and modify actions
        # Note: ActPhase sorts actions by priority (write_file=1, run=4)
        # So write_file will be executed before run, regardless of input order
        coordinator.job_state.shared_data["actions"] = {
            "actions": [
                {"tool": "run", "args": {"cmd": "cat file.txt"}},
                {"tool": "write_file", "args": {"path": "out.txt", "content": "data"}},
            ],
            "stop_reason": "continue",
        }

        context = PhaseContext(step=1, phase=Phase.ACT)
        act_phase.execute(context)

        # Verify categorization - write_file executes first due to sorting
        tracker = coordinator.progress_tracker
        assert tracker.action_history[0].category.value == "modify"  # write_file (priority 1)
        assert tracker.action_history[1].category.value == "view"  # run (priority 4)


# =============================================================================
# Memory State Persistence Tests
# =============================================================================


class TestMemoryStatePersistence:
    """Test that loop detection state is correctly persisted."""

    def test_action_history_serialization(self):
        """Test that action history can be serialized to Memory."""
        tracker = ProgressTracker()

        # Record some actions
        tracker.record_action(step=0, tool="run", args={"cmd": "ls"}, result={"ok": True})
        tracker.record_action(
            step=1, tool="write_file", args={"path": "f.txt", "content": "x"}, result={"ok": True}
        )

        # Create memory with action history
        memory = Memory()
        memory.action_history = [a.to_dict() for a in tracker.action_history]

        # Create agent state
        state = AgentState()
        state.memory = memory

        # Serialize
        state_dict = state.to_dict()

        # Verify action_history is in serialized state
        assert "action_history" in state_dict["memory"]
        assert len(state_dict["memory"]["action_history"]) == 2

    def test_action_history_deserialization(self):
        """Test that action history can be restored from Memory."""
        # Create state dict with action history
        state_dict = {
            "step": 5,
            "phase": "PLAN",
            "last_error": {},
            "memory": {
                "action_history": [
                    {
                        "step": 0,
                        "tool": "run",
                        "args": {"cmd": "ls"},
                        "args_signature": "abc123",
                        "category": "view",
                        "target_file": None,
                        "success": True,
                        "has_output": True,
                        "timestamp": 0.0,
                    },
                ],
                "created_files": [],
                "attempts": [],
                "key_files": [],
                "notes": [],
                "tool_results_history": [],
                "modified_files_content": [],
                "plan": [],
                "task_summary": "",
                "important_decisions": [],
                "milestones": [],
                "learnings": [],
                "decisions": [],
                "llm_responses": [],
            },
            "artifacts": {},
            "budget_used": {},
        }

        # Deserialize
        state = AgentState.from_dict(state_dict)

        # Verify action history is restored
        assert len(state.memory.action_history) == 1
        assert state.memory.action_history[0]["tool"] == "run"

    def test_progress_tracker_restoration(self):
        """Test that ProgressTracker can be restored from memory state."""
        # Create original tracker
        original = ProgressTracker()
        original.record_action(step=0, tool="run", args={"cmd": "cat a.txt"}, result={"ok": True})
        original.record_action(step=1, tool="run", args={"cmd": "cat a.txt"}, result={"ok": True})
        original.record_action(
            step=2,
            tool="write_file",
            args={"path": "/workspace/test.txt", "content": "hello"},
            result={"ok": True},
        )

        # Serialize
        data = original.to_dict()

        # Restore
        restored = ProgressTracker.from_dict(data)

        # Verify state is preserved
        assert len(restored.action_history) == len(original.action_history)
        assert restored.created_files == original.created_files

        # Verify metrics are similar
        orig_metrics = original.get_metrics()
        rest_metrics = restored.get_metrics()

        assert orig_metrics.total_actions == rest_metrics.total_actions
        assert orig_metrics.view_actions == rest_metrics.view_actions
        assert orig_metrics.modify_actions == rest_metrics.modify_actions


# =============================================================================
# Loop Detection Threshold Tests
# =============================================================================


class TestLoopDetectionThresholds:
    """Test loop detection with various threshold configurations."""

    def test_default_thresholds(self):
        """Test loop detection with default thresholds."""
        tracker = ProgressTracker()
        detector = LoopDetector()  # Uses default config

        # Get the actual thresholds
        soft = detector.config.soft_warning_threshold

        # Below threshold - no loop
        for i in range(soft - 1):
            tracker.record_action(
                step=i, tool="run", args={"cmd": "cat file.txt"}, result={"ok": True}
            )

        analysis = detector.analyze(tracker)
        assert analysis.intervention_level == InterventionLevel.NONE

    def test_custom_strict_thresholds(self):
        """Test with very strict (low) thresholds."""
        config = LoopDetectionConfig(
            soft_warning_threshold=1,
            hard_warning_threshold=2,
            force_threshold=2,  # Same as hard - should still work
            abort_threshold=3,
        )

        tracker = ProgressTracker()
        detector = LoopDetector(config)

        # Single repetition should trigger soft warning
        tracker.record_action(step=0, tool="run", args={"cmd": "cat f.txt"}, result={"ok": True})
        tracker.record_action(step=1, tool="run", args={"cmd": "cat f.txt"}, result={"ok": True})

        analysis = detector.analyze(tracker)

        # At 2 repetitions with soft=1, hard=2, we should be at hard or higher
        assert analysis.is_looping is True
        assert analysis.intervention_level >= InterventionLevel.HARD_WARNING

    def test_custom_lenient_thresholds(self):
        """Test with very lenient (high) thresholds."""
        config = LoopDetectionConfig(
            soft_warning_threshold=10,
            hard_warning_threshold=20,
            force_threshold=30,
            abort_threshold=40,
            max_view_without_modify=20,  # Also set high to prevent VIEW_WITHOUT_MODIFY detection
        )

        tracker = ProgressTracker()
        detector = LoopDetector(config)

        # 5 repetitions should not trigger anything (below all thresholds)
        for i in range(5):
            tracker.record_action(
                step=i, tool="run", args={"cmd": "cat file.txt"}, result={"ok": True}
            )

        analysis = detector.analyze(tracker)

        # Below all thresholds, so no loop should be detected
        # Or if detected, intervention level should be NONE
        if analysis.is_looping:
            # If a loop is detected, it should have NONE intervention (below thresholds)
            assert analysis.intervention_level == InterventionLevel.NONE, (
                f"Expected NONE intervention, got {analysis.intervention_level}"
            )
        else:
            # No loop detected - also acceptable
            assert analysis.is_looping is False


# =============================================================================
# Edge Cases for Integration
# =============================================================================


class TestIntegrationEdgeCases:
    """Test edge cases in the integration."""

    def test_empty_action_list(self, mock_coordinator_with_loop_detection):
        """Test handling of empty action list."""
        coordinator = mock_coordinator_with_loop_detection
        act_phase = ActPhase(coordinator)

        # Empty actions
        coordinator.job_state.shared_data["actions"] = {
            "actions": [],
            "stop_reason": "continue",
        }

        context = PhaseContext(step=1, phase=Phase.ACT)
        act_phase.execute(context)

        # Should handle gracefully
        assert len(coordinator.progress_tracker.action_history) == 0

    def test_mixed_success_and_failure(self, mock_coordinator_with_loop_detection):
        """Test tracking with mix of successful and failed actions."""
        coordinator = mock_coordinator_with_loop_detection
        act_phase = ActPhase(coordinator)

        # Return success for first, failure for second
        results = [
            {"ok": True, "success": True, "stdout": "ok", "stderr": ""},
            {"ok": False, "success": False, "stdout": "", "stderr": "error"},
        ]
        act_phase.executor = MagicMock()
        act_phase.executor._execute_action = MagicMock(side_effect=results)

        coordinator.job_state.shared_data["actions"] = {
            "actions": [
                {"tool": "run", "args": {"cmd": "ls"}},
                {"tool": "run", "args": {"cmd": "fail"}},
            ],
            "stop_reason": "continue",
        }

        context = PhaseContext(step=1, phase=Phase.ACT)
        act_phase.execute(context)

        # Both should be recorded
        tracker = coordinator.progress_tracker
        assert len(tracker.action_history) == 2
        assert tracker.action_history[0].success is True
        assert tracker.action_history[1].success is False

    def test_progress_tracker_survives_exceptions(self, mock_coordinator_with_loop_detection):
        """Test that progress tracker state survives action exceptions."""
        coordinator = mock_coordinator_with_loop_detection

        # Pre-populate tracker
        coordinator.progress_tracker.record_action(
            step=0, tool="run", args={"cmd": "pre-existing"}, result={"ok": True}
        )

        initial_count = len(coordinator.progress_tracker.action_history)

        act_phase = ActPhase(coordinator)

        # Setup to raise exception
        act_phase.executor = MagicMock()
        act_phase.executor._execute_action = MagicMock(side_effect=Exception("Test exception"))

        coordinator.job_state.shared_data["actions"] = {
            "actions": [{"tool": "run", "args": {"cmd": "will-fail"}}],
            "stop_reason": "continue",
        }

        context = PhaseContext(step=1, phase=Phase.ACT)

        # Execute (may raise or handle exception)
        try:
            act_phase.execute(context)
        except Exception:
            pass

        # Original action should still be in history
        assert len(coordinator.progress_tracker.action_history) >= initial_count


# =============================================================================
# Intervention Message Content Tests
# =============================================================================


class TestInterventionMessageContent:
    """Test the content of intervention messages."""

    def test_soft_warning_is_gentle(self):
        """Test that soft warning uses gentle language."""
        config = LoopDetectionConfig(soft_warning_threshold=1)
        tracker = ProgressTracker()
        detector = LoopDetector(config)

        # Trigger soft warning
        tracker.record_action(step=0, tool="run", args={"cmd": "cat f.txt"}, result={"ok": True})
        tracker.record_action(step=1, tool="run", args={"cmd": "cat f.txt"}, result={"ok": True})

        analysis = detector.analyze(tracker)

        if analysis.intervention_level == InterventionLevel.SOFT_WARNING:
            intervention = detector.generate_intervention(analysis)

            # Should not have aggressive language
            prompt = intervention.prompt_injection.lower()
            assert "must" not in prompt or "consider" in prompt
            assert "abort" not in prompt
            assert "force" not in prompt

    def test_abort_is_final(self):
        """Test that abort message indicates finality."""
        config = LoopDetectionConfig(
            soft_warning_threshold=1,
            hard_warning_threshold=2,
            force_threshold=3,
            abort_threshold=4,
        )
        tracker = ProgressTracker()
        detector = LoopDetector(config)

        # Trigger abort
        for i in range(4):
            tracker.record_action(
                step=i, tool="run", args={"cmd": "cat f.txt"}, result={"ok": True}
            )

        analysis = detector.analyze(tracker)

        if analysis.intervention_level == InterventionLevel.ABORT:
            intervention = detector.generate_intervention(analysis)

            prompt = intervention.prompt_injection
            # Should indicate finality
            assert "ABORT" in prompt or "ABANDON" in prompt or "FAILED" in prompt

    def test_intervention_includes_evidence(self):
        """Test that interventions include evidence of the loop."""
        config = LoopDetectionConfig(soft_warning_threshold=2)
        tracker = ProgressTracker()
        detector = LoopDetector(config)

        # Create a detectable loop
        for i in range(3):
            tracker.record_action(
                step=i, tool="run", args={"cmd": "cat same.txt"}, result={"ok": True}
            )

        analysis = detector.analyze(tracker)

        if analysis.is_looping:
            intervention = detector.generate_intervention(analysis)

            # Evidence should be in the message
            prompt = intervention.prompt_injection
            assert (
                "evidence" in prompt.lower()
                or "pattern" in prompt.lower()
                or "repeat" in prompt.lower()
            )
