"""
Tests for LoopInterventionExecutor.

These tests verify the centralized intervention execution logic.
"""

import pytest
from unittest.mock import MagicMock

from atloop.config.loop_detection import InterventionLevel, LoopDetectionConfig
from atloop.memory.progress_tracker import ProgressMetrics
from atloop.orchestrator.loop_detector import (
    Intervention,
    LoopAnalysis,
    LoopType,
)
from atloop.orchestrator.loop_intervention_executor import (
    InterventionAction,
    InterventionResult,
    LoopInterventionExecutor,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def executor() -> LoopInterventionExecutor:
    """Create a default executor."""
    return LoopInterventionExecutor(workspace_path="/workspace")


@pytest.fixture
def no_loop_analysis() -> LoopAnalysis:
    """Create analysis indicating no loop."""
    return LoopAnalysis(
        is_looping=False,
        loop_type=LoopType.NONE,
        intervention_level=InterventionLevel.NONE,
        repetition_count=0,
        evidence=[],
    )


@pytest.fixture
def soft_warning_analysis() -> LoopAnalysis:
    """Create analysis for soft warning level."""
    return LoopAnalysis(
        is_looping=True,
        loop_type=LoopType.VIEW_WITHOUT_MODIFY,
        intervention_level=InterventionLevel.SOFT_WARNING,
        repetition_count=2,
        evidence=["Viewed files 2 times without modification"],
    )


@pytest.fixture
def hard_warning_analysis() -> LoopAnalysis:
    """Create analysis for hard warning level."""
    return LoopAnalysis(
        is_looping=True,
        loop_type=LoopType.VIEW_WITHOUT_MODIFY,
        intervention_level=InterventionLevel.HARD_WARNING,
        repetition_count=4,
        evidence=["Viewed files 4 times without modification"],
    )


@pytest.fixture
def force_strategy_analysis() -> LoopAnalysis:
    """Create analysis for force strategy level."""
    return LoopAnalysis(
        is_looping=True,
        loop_type=LoopType.VIEW_WITHOUT_MODIFY,
        intervention_level=InterventionLevel.FORCE_STRATEGY,
        repetition_count=7,  # Above FORCE_REPETITION_THRESHOLD (6)
        evidence=["Viewed files 7 times without modification"],
    )


@pytest.fixture
def abort_analysis() -> LoopAnalysis:
    """Create analysis for abort level."""
    return LoopAnalysis(
        is_looping=True,
        loop_type=LoopType.VIEW_WITHOUT_MODIFY,
        intervention_level=InterventionLevel.ABORT,
        repetition_count=15,  # Above ABORT_REPETITION_THRESHOLD (12)
        evidence=["Viewed files 15 times without modification"],
    )


def create_intervention(level: InterventionLevel, prompt: str = "Warning") -> Intervention:
    """Helper to create interventions."""
    return Intervention(
        level=level,
        message="Test intervention",
        prompt_injection=prompt,
    )


# =============================================================================
# Tests for InterventionResult
# =============================================================================

class TestInterventionResult:
    """Tests for InterventionResult dataclass."""

    def test_should_skip_llm_for_force_recovery(self):
        """Force recovery should skip LLM."""
        result = InterventionResult(
            action=InterventionAction.FORCE_RECOVERY,
            prompt_injection="",
            forced_actions=[{"tool": "run", "args": {"cmd": "ls"}}],
            error_message="",
            analysis=None,
        )
        assert result.should_skip_llm is True
        assert result.should_abort is False

    def test_should_skip_llm_for_abort(self):
        """Abort should skip LLM."""
        result = InterventionResult(
            action=InterventionAction.ABORT_TASK,
            prompt_injection="",
            forced_actions=[],
            error_message="Task aborted",
            analysis=None,
        )
        assert result.should_skip_llm is True
        assert result.should_abort is True

    def test_should_not_skip_llm_for_warning(self):
        """Warning should not skip LLM."""
        result = InterventionResult(
            action=InterventionAction.INJECT_WARNING,
            prompt_injection="Warning text",
            forced_actions=[],
            error_message="",
            analysis=None,
        )
        assert result.should_skip_llm is False
        assert result.should_abort is False

    def test_should_not_skip_llm_for_normal(self):
        """Normal operation should not skip LLM."""
        result = InterventionResult(
            action=InterventionAction.CONTINUE_NORMAL,
            prompt_injection="",
            forced_actions=[],
            error_message="",
            analysis=None,
        )
        assert result.should_skip_llm is False
        assert result.should_abort is False


# =============================================================================
# Tests for LoopInterventionExecutor
# =============================================================================

class TestLoopInterventionExecutor:
    """Tests for LoopInterventionExecutor."""

    def test_no_loop_returns_continue_normal(self, executor, no_loop_analysis):
        """No loop detected should return CONTINUE_NORMAL."""
        intervention = create_intervention(InterventionLevel.NONE, "")
        
        result = executor.execute(no_loop_analysis, intervention)
        
        assert result.action == InterventionAction.CONTINUE_NORMAL
        assert result.prompt_injection == ""
        assert result.forced_actions == []
        assert not result.should_skip_llm

    def test_soft_warning_returns_inject_warning(self, executor, soft_warning_analysis):
        """Soft warning should return INJECT_WARNING."""
        intervention = create_intervention(
            InterventionLevel.SOFT_WARNING,
            "## Warning\nYou are repeating actions."
        )
        
        result = executor.execute(soft_warning_analysis, intervention)
        
        assert result.action == InterventionAction.INJECT_WARNING
        assert "Warning" in result.prompt_injection
        assert not result.should_skip_llm

    def test_hard_warning_returns_inject_warning(self, executor, hard_warning_analysis):
        """Hard warning should still return INJECT_WARNING (below threshold)."""
        intervention = create_intervention(
            InterventionLevel.HARD_WARNING,
            "## CRITICAL WARNING\nStop repeating!"
        )
        
        result = executor.execute(hard_warning_analysis, intervention)
        
        assert result.action == InterventionAction.INJECT_WARNING
        assert "CRITICAL" in result.prompt_injection
        assert not result.should_skip_llm

    def test_force_strategy_with_high_repetitions_returns_force_recovery(
        self, executor, force_strategy_analysis
    ):
        """Force strategy with high repetitions should return FORCE_RECOVERY."""
        intervention = create_intervention(
            InterventionLevel.FORCE_STRATEGY,
            "## FORCED RECOVERY\nSystem is taking over."
        )
        
        result = executor.execute(force_strategy_analysis, intervention)
        
        assert result.action == InterventionAction.FORCE_RECOVERY
        assert len(result.forced_actions) > 0
        assert result.should_skip_llm

    def test_abort_with_high_repetitions_returns_abort(self, executor, abort_analysis):
        """Abort with high repetitions should return ABORT_TASK."""
        intervention = create_intervention(
            InterventionLevel.ABORT,
            "## ABORT\nTask is being terminated."
        )
        
        result = executor.execute(abort_analysis, intervention)
        
        assert result.action == InterventionAction.ABORT_TASK
        assert result.should_abort
        assert len(result.error_message) > 0
        assert "Unbreakable loop" in result.error_message

    def test_force_recovery_generates_meaningful_actions(self, executor):
        """Force recovery should generate meaningful actions based on loop type."""
        analysis = LoopAnalysis(
            is_looping=True,
            loop_type=LoopType.VIEW_WITHOUT_MODIFY,
            intervention_level=InterventionLevel.FORCE_STRATEGY,
            repetition_count=8,
            evidence=["Viewed files without modification"],
        )
        intervention = create_intervention(InterventionLevel.FORCE_STRATEGY, "")
        
        result = executor.execute(analysis, intervention)
        
        assert result.action == InterventionAction.FORCE_RECOVERY
        assert len(result.forced_actions) > 0
        
        # Check that forced action contains relevant information
        action = result.forced_actions[0]
        assert action["tool"] == "run"
        assert "VIEW_WITHOUT_MODIFY" in action["args"]["cmd"]

    def test_same_action_repeat_generates_different_recovery(self, executor):
        """Same action repeat should generate different recovery than view_without_modify."""
        analysis = LoopAnalysis(
            is_looping=True,
            loop_type=LoopType.SAME_ACTION_REPEAT,
            intervention_level=InterventionLevel.FORCE_STRATEGY,
            repetition_count=8,
            evidence=["Same action repeated"],
        )
        intervention = create_intervention(InterventionLevel.FORCE_STRATEGY, "")
        
        result = executor.execute(analysis, intervention)
        
        assert result.action == InterventionAction.FORCE_RECOVERY
        action = result.forced_actions[0]
        assert "SAME_ACTION_REPEAT" in action["args"]["cmd"]

    def test_thresholds_are_respected(self, executor):
        """Verify that thresholds are respected."""
        # Below FORCE threshold (6), should return warning
        low_rep_analysis = LoopAnalysis(
            is_looping=True,
            loop_type=LoopType.VIEW_WITHOUT_MODIFY,
            intervention_level=InterventionLevel.FORCE_STRATEGY,
            repetition_count=5,  # Below threshold
            evidence=["Test"],
        )
        intervention = create_intervention(InterventionLevel.FORCE_STRATEGY, "Warning")
        
        result = executor.execute(low_rep_analysis, intervention)
        
        # Should still be warning since repetitions below threshold
        assert result.action == InterventionAction.INJECT_WARNING

    def test_abort_threshold_respected(self, executor):
        """Verify abort threshold is respected."""
        # At ABORT level but below threshold
        low_rep_abort = LoopAnalysis(
            is_looping=True,
            loop_type=LoopType.VIEW_WITHOUT_MODIFY,
            intervention_level=InterventionLevel.ABORT,
            repetition_count=10,  # Below ABORT_REPETITION_THRESHOLD (12)
            evidence=["Test"],
        )
        intervention = create_intervention(InterventionLevel.ABORT, "Warning")
        
        result = executor.execute(low_rep_abort, intervention)
        
        # Should force recovery, not abort
        assert result.action == InterventionAction.FORCE_RECOVERY


# =============================================================================
# Integration Tests
# =============================================================================

class TestInterventionExecutorIntegration:
    """Integration tests for intervention executor with real detector."""

    def test_full_flow_from_tracker_to_intervention(self):
        """Test the full flow from progress tracking to intervention execution."""
        from atloop.memory.progress_tracker import ProgressTracker
        from atloop.orchestrator.loop_detector import LoopDetector
        
        # Setup
        tracker = ProgressTracker()
        detector = LoopDetector()
        executor = LoopInterventionExecutor()
        
        # Simulate VIEW_WITHOUT_MODIFY loop
        for i in range(10):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": "cat file.txt"},
                result={"ok": True},
            )
        
        # Analyze
        analysis = detector.analyze(tracker)
        
        # Generate intervention
        intervention = detector.generate_intervention(analysis)
        
        # Execute intervention
        result = executor.execute(analysis, intervention)
        
        # Should be either FORCE_RECOVERY or INJECT_WARNING based on thresholds
        assert result.action in [
            InterventionAction.FORCE_RECOVERY,
            InterventionAction.INJECT_WARNING,
        ]

    def test_normal_workflow_no_intervention(self):
        """Test that normal workflow doesn't trigger intervention."""
        from atloop.memory.progress_tracker import ProgressTracker
        from atloop.orchestrator.loop_detector import LoopDetector
        
        tracker = ProgressTracker()
        detector = LoopDetector()
        executor = LoopInterventionExecutor()
        
        # Normal workflow with varied actions
        tracker.record_action(step=0, tool="run", args={"cmd": "ls"}, result={"ok": True})
        tracker.record_action(step=1, tool="write_file", args={"path": "f.txt"}, result={"ok": True})
        tracker.record_action(step=2, tool="run", args={"cmd": "cat f.txt"}, result={"ok": True})
        
        analysis = detector.analyze(tracker)
        intervention = detector.generate_intervention(analysis)
        result = executor.execute(analysis, intervention)
        
        assert result.action == InterventionAction.CONTINUE_NORMAL
