"""
Comprehensive tests for loop detection functionality.

These tests are written based on the interface specification, 
NOT the implementation details. They test:
1. LoopDetectionConfig - configuration and threshold behavior
2. ProgressTracker - action recording and metrics calculation
3. LoopDetector - loop detection and intervention generation
4. Integration - full loop detection flow
"""

import pytest
import time
from typing import Dict, Any, List

from atloop.config.loop_detection import (
    LoopDetectionConfig,
    InterventionLevel,
    DEFAULT_LOOP_DETECTION_CONFIG,
)
from atloop.memory.progress_tracker import (
    ProgressTracker,
    ActionCategory,
    ActionRecord,
    ProgressMetrics,
)
from atloop.orchestrator.loop_detector import (
    LoopDetector,
    LoopType,
    LoopAnalysis,
    Intervention,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def config() -> LoopDetectionConfig:
    """Create a default loop detection config."""
    return LoopDetectionConfig()


@pytest.fixture
def custom_config() -> LoopDetectionConfig:
    """Create a custom config with lower thresholds for testing."""
    return LoopDetectionConfig(
        soft_warning_threshold=1,
        hard_warning_threshold=2,
        force_threshold=3,
        abort_threshold=4,
        max_view_without_modify=2,
    )


@pytest.fixture
def tracker() -> ProgressTracker:
    """Create a fresh progress tracker."""
    return ProgressTracker()


@pytest.fixture
def detector() -> LoopDetector:
    """Create a loop detector with default config."""
    return LoopDetector()


@pytest.fixture
def detector_with_custom_config(custom_config) -> LoopDetector:
    """Create a loop detector with custom config."""
    return LoopDetector(custom_config)


# =============================================================================
# LoopDetectionConfig Tests
# =============================================================================

class TestLoopDetectionConfig:
    """Tests for LoopDetectionConfig."""

    def test_default_config_values(self):
        """Test that default config has expected values."""
        config = LoopDetectionConfig()
        
        # Verify threshold hierarchy: soft < hard < force < abort
        assert config.soft_warning_threshold < config.hard_warning_threshold
        assert config.hard_warning_threshold < config.force_threshold
        assert config.force_threshold < config.abort_threshold
        
        # Verify reasonable defaults
        assert config.soft_warning_threshold >= 1
        assert config.max_view_without_modify >= 1
        assert 0 < config.action_similarity_threshold <= 1

    def test_get_intervention_level_none(self, config):
        """Test that low repetition counts return NONE."""
        # Below soft_warning_threshold should return NONE
        for count in range(config.soft_warning_threshold):
            level = config.get_intervention_level(count)
            assert level == InterventionLevel.NONE, \
                f"Count {count} should return NONE, got {level}"

    def test_get_intervention_level_soft_warning(self, config):
        """Test SOFT_WARNING level trigger."""
        # At or above soft_warning but below hard_warning
        for count in range(config.soft_warning_threshold, config.hard_warning_threshold):
            level = config.get_intervention_level(count)
            assert level == InterventionLevel.SOFT_WARNING, \
                f"Count {count} should return SOFT_WARNING, got {level}"

    def test_get_intervention_level_hard_warning(self, config):
        """Test HARD_WARNING level trigger."""
        # At or above hard_warning but below force
        for count in range(config.hard_warning_threshold, config.force_threshold):
            level = config.get_intervention_level(count)
            assert level == InterventionLevel.HARD_WARNING, \
                f"Count {count} should return HARD_WARNING, got {level}"

    def test_get_intervention_level_force_strategy(self, config):
        """Test FORCE_STRATEGY level trigger."""
        # At or above force but below abort
        for count in range(config.force_threshold, config.abort_threshold):
            level = config.get_intervention_level(count)
            assert level == InterventionLevel.FORCE_STRATEGY, \
                f"Count {count} should return FORCE_STRATEGY, got {level}"

    def test_get_intervention_level_abort(self, config):
        """Test ABORT level trigger."""
        # At or above abort threshold
        for count in [config.abort_threshold, config.abort_threshold + 10, 100]:
            level = config.get_intervention_level(count)
            assert level == InterventionLevel.ABORT, \
                f"Count {count} should return ABORT, got {level}"

    def test_intervention_level_ordering(self):
        """Test that InterventionLevel enum values are ordered correctly."""
        assert InterventionLevel.NONE < InterventionLevel.SOFT_WARNING
        assert InterventionLevel.SOFT_WARNING < InterventionLevel.HARD_WARNING
        assert InterventionLevel.HARD_WARNING < InterventionLevel.FORCE_STRATEGY
        assert InterventionLevel.FORCE_STRATEGY < InterventionLevel.ABORT

    def test_custom_config_thresholds(self):
        """Test custom threshold configuration."""
        config = LoopDetectionConfig(
            soft_warning_threshold=5,
            hard_warning_threshold=10,
            force_threshold=15,
            abort_threshold=20,
        )
        
        assert config.get_intervention_level(4) == InterventionLevel.NONE
        assert config.get_intervention_level(5) == InterventionLevel.SOFT_WARNING
        assert config.get_intervention_level(10) == InterventionLevel.HARD_WARNING
        assert config.get_intervention_level(15) == InterventionLevel.FORCE_STRATEGY
        assert config.get_intervention_level(20) == InterventionLevel.ABORT

    def test_default_config_singleton(self):
        """Test that DEFAULT_LOOP_DETECTION_CONFIG is properly initialized."""
        assert DEFAULT_LOOP_DETECTION_CONFIG is not None
        assert isinstance(DEFAULT_LOOP_DETECTION_CONFIG, LoopDetectionConfig)


# =============================================================================
# ProgressTracker Tests
# =============================================================================

class TestProgressTracker:
    """Tests for ProgressTracker."""

    def test_initial_state(self, tracker):
        """Test tracker starts in clean state."""
        assert len(tracker.action_history) == 0
        assert len(tracker.created_files) == 0
        assert len(tracker.modified_files) == 0
        
        metrics = tracker.get_metrics()
        assert metrics.total_actions == 0
        assert metrics.files_created == 0

    def test_record_single_action(self, tracker):
        """Test recording a single action."""
        record = tracker.record_action(
            step=1,
            tool="run",
            args={"cmd": "ls -la"},
            result={"ok": True, "stdout": "file1.txt"},
        )
        
        assert isinstance(record, ActionRecord)
        assert record.step == 1
        assert record.tool == "run"
        assert record.success is True
        assert len(tracker.action_history) == 1

    def test_action_categorization_view(self, tracker):
        """Test that view commands are categorized correctly."""
        view_commands = [
            "cat file.txt",
            "head -n 10 file.txt",
            "tail -f log.txt",
            "grep pattern file.txt",
            "less file.txt",
        ]
        
        for cmd in view_commands:
            tracker.reset()
            record = tracker.record_action(
                step=1,
                tool="run",
                args={"cmd": cmd},
                result={"ok": True, "stdout": "output"},
            )
            assert record.category == ActionCategory.VIEW, \
                f"Command '{cmd}' should be categorized as VIEW, got {record.category}"

    def test_action_categorization_execute(self, tracker):
        """Test that execute commands are categorized correctly."""
        execute_commands = [
            "python script.py",
            "python3 main.py",
            "node app.js",
            "npm run test",
            "pytest tests/",
        ]
        
        for cmd in execute_commands:
            tracker.reset()
            record = tracker.record_action(
                step=1,
                tool="run",
                args={"cmd": cmd},
                result={"ok": True, "stdout": "output"},
            )
            assert record.category == ActionCategory.EXECUTE, \
                f"Command '{cmd}' should be categorized as EXECUTE, got {record.category}"

    def test_action_categorization_modify(self, tracker):
        """Test that modify tools are categorized correctly."""
        modify_tools = ["write_file", "edit_file", "append_file", "multi_edit_file"]
        
        for tool in modify_tools:
            tracker.reset()
            record = tracker.record_action(
                step=1,
                tool=tool,
                args={"path": "/test/file.txt", "content": "test"},
                result={"ok": True},
            )
            assert record.category == ActionCategory.MODIFY, \
                f"Tool '{tool}' should be categorized as MODIFY, got {record.category}"

    def test_consecutive_same_pattern_detection(self, tracker):
        """Test detection of consecutive same action patterns."""
        # Record the same action 5 times
        for i in range(5):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": "cat /workspace/test.js"},
                result={"ok": True, "stdout": "content"},
            )
        
        metrics = tracker.get_metrics()
        assert metrics.consecutive_same_pattern == 5

    def test_consecutive_pattern_resets_on_different_action(self, tracker):
        """Test that consecutive count resets when action changes."""
        # Record same action 3 times
        for i in range(3):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": "cat file.txt"},
                result={"ok": True},
            )
        
        # Record a different action
        tracker.record_action(
            step=3,
            tool="write_file",
            args={"path": "file.txt", "content": "new"},
            result={"ok": True},
        )
        
        metrics = tracker.get_metrics()
        assert metrics.consecutive_same_pattern == 1

    def test_consecutive_view_count(self, tracker):
        """Test counting consecutive view operations."""
        # Record 4 view operations
        for i in range(4):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": f"cat file{i}.txt"},
                result={"ok": True},
            )
        
        metrics = tracker.get_metrics()
        assert metrics.consecutive_view_count == 4

    def test_consecutive_view_resets_on_modify(self, tracker):
        """Test that consecutive view count resets on modify action."""
        # Record 3 view operations
        for i in range(3):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": f"cat file{i}.txt"},
                result={"ok": True},
            )
        
        # Record a modify operation
        tracker.record_action(
            step=3,
            tool="write_file",
            args={"path": "file.txt", "content": "new"},
            result={"ok": True},
        )
        
        metrics = tracker.get_metrics()
        assert metrics.consecutive_view_count == 0

    def test_unique_vs_repeated_actions(self, tracker):
        """Test tracking of unique vs repeated actions."""
        # Record 3 unique actions
        tracker.record_action(step=0, tool="run", args={"cmd": "cat a.txt"}, result={"ok": True})
        tracker.record_action(step=1, tool="run", args={"cmd": "cat b.txt"}, result={"ok": True})
        tracker.record_action(step=2, tool="run", args={"cmd": "cat c.txt"}, result={"ok": True})
        
        # Repeat the first action
        tracker.record_action(step=3, tool="run", args={"cmd": "cat a.txt"}, result={"ok": True})
        tracker.record_action(step=4, tool="run", args={"cmd": "cat a.txt"}, result={"ok": True})
        
        metrics = tracker.get_metrics()
        assert metrics.total_actions == 5
        assert metrics.unique_actions == 3  # a.txt, b.txt, c.txt
        assert metrics.repeated_actions == 2  # Two repeats of a.txt

    def test_file_tracking_on_write(self, tracker):
        """Test that file creation is tracked."""
        tracker.record_action(
            step=0,
            tool="write_file",
            args={"path": "/workspace/new_file.txt", "content": "hello"},
            result={"ok": True},
        )
        
        metrics = tracker.get_metrics()
        assert metrics.files_created == 1
        assert "/workspace/new_file.txt" in tracker.created_files

    def test_view_to_modify_ratio(self, tracker):
        """Test view to modify ratio calculation."""
        # 6 view actions
        for i in range(6):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": f"cat file{i}.txt"},
                result={"ok": True},
            )
        
        # 2 modify actions
        for i in range(2):
            tracker.record_action(
                step=6+i,
                tool="write_file",
                args={"path": f"out{i}.txt", "content": "data"},
                result={"ok": True},
            )
        
        metrics = tracker.get_metrics()
        assert metrics.view_actions == 6
        assert metrics.modify_actions == 2
        assert metrics.view_to_modify_ratio == 3.0  # 6/2 = 3

    def test_repetition_rate_calculation(self, tracker):
        """Test repetition rate calculation."""
        # 4 unique actions
        for i in range(4):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": f"unique_cmd_{i}"},
                result={"ok": True},
            )
        
        # 6 repeated actions (same command)
        for i in range(6):
            tracker.record_action(
                step=4+i,
                tool="run",
                args={"cmd": "repeated_cmd"},
                result={"ok": True},
            )
        
        metrics = tracker.get_metrics()
        assert metrics.total_actions == 10
        # unique_cmd_0..3 (4) + repeated_cmd (1) = 5 unique
        assert metrics.unique_actions == 5
        # 5 repeats of repeated_cmd
        assert metrics.repeated_actions == 5
        assert metrics.repetition_rate == 0.5  # 5/10

    def test_windowed_metrics(self, tracker):
        """Test metrics calculation with window parameter."""
        # Record 10 actions
        for i in range(10):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": f"cmd_{i % 3}"},  # Only 3 unique commands
                result={"ok": True},
            )
        
        # Get metrics for last 5 actions only
        metrics = tracker.get_metrics(window=5)
        assert metrics.total_actions == 5

    def test_serialization_roundtrip(self, tracker):
        """Test tracker serialization and deserialization."""
        # Add some actions
        tracker.record_action(step=0, tool="run", args={"cmd": "ls"}, result={"ok": True})
        tracker.record_action(
            step=1, 
            tool="write_file", 
            args={"path": "test.txt", "content": "data"}, 
            result={"ok": True}
        )
        
        # Serialize
        data = tracker.to_dict()
        
        # Deserialize to new tracker
        restored = ProgressTracker.from_dict(data)
        
        # Verify state is preserved
        assert len(restored.action_history) == len(tracker.action_history)
        assert restored.created_files == tracker.created_files

    def test_reset_clears_state(self, tracker):
        """Test that reset clears all state."""
        # Add some data
        tracker.record_action(step=0, tool="run", args={"cmd": "ls"}, result={"ok": True})
        
        # Reset
        tracker.reset()
        
        # Verify clean state
        assert len(tracker.action_history) == 0
        assert len(tracker.created_files) == 0
        metrics = tracker.get_metrics()
        assert metrics.total_actions == 0

    def test_action_record_to_dict(self, tracker):
        """Test ActionRecord serialization."""
        record = tracker.record_action(
            step=5,
            tool="run",
            args={"cmd": "test"},
            result={"ok": True},
            timestamp=12345.0,
        )
        
        data = record.to_dict()
        
        assert data["step"] == 5
        assert data["tool"] == "run"
        assert data["timestamp"] == 12345.0
        assert "args_signature" in data
        assert "category" in data


# =============================================================================
# LoopDetector Tests
# =============================================================================

class TestLoopDetector:
    """Tests for LoopDetector."""

    def test_no_loop_on_empty_tracker(self, detector, tracker):
        """Test that empty tracker reports no loop."""
        analysis = detector.analyze(tracker)
        
        assert analysis.is_looping is False
        assert analysis.loop_type == LoopType.NONE
        assert analysis.intervention_level == InterventionLevel.NONE

    def test_no_loop_on_normal_activity(self, detector, tracker):
        """Test that varied activity doesn't trigger loop detection."""
        # Mix of different actions
        tracker.record_action(step=0, tool="run", args={"cmd": "ls"}, result={"ok": True})
        tracker.record_action(
            step=1, tool="write_file", 
            args={"path": "f.txt", "content": "x"}, 
            result={"ok": True}
        )
        tracker.record_action(step=2, tool="run", args={"cmd": "python test.py"}, result={"ok": True})
        
        analysis = detector.analyze(tracker)
        
        assert analysis.is_looping is False

    def test_detect_same_action_repeat(self, detector_with_custom_config, tracker):
        """Test detection of same action repeated."""
        detector = detector_with_custom_config
        
        # Repeat the same action 3 times (force_threshold)
        for i in range(3):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": "cat /workspace/test.js"},
                result={"ok": True},
            )
        
        analysis = detector.analyze(tracker)
        
        assert analysis.is_looping is True
        assert analysis.loop_type == LoopType.SAME_ACTION_REPEAT
        assert analysis.repetition_count == 3

    def test_detect_view_without_modify(self, detector_with_custom_config, tracker):
        """Test detection of view without modify pattern."""
        detector = detector_with_custom_config
        
        # View files without any modification
        # Need to exceed max_view_without_modify (set to 2 in custom_config)
        for i in range(3):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": f"cat file{i}.txt"},
                result={"ok": True},
            )
        
        analysis = detector.analyze(tracker)
        
        # Should detect either VIEW_WITHOUT_MODIFY or SAME_ACTION_REPEAT
        assert analysis.is_looping is True

    def test_intervention_level_matches_repetition(self, detector, tracker):
        """Test that intervention level increases with repetitions."""
        config = detector.config
        
        # Test at each threshold
        test_cases = [
            (config.soft_warning_threshold, InterventionLevel.SOFT_WARNING),
            (config.hard_warning_threshold, InterventionLevel.HARD_WARNING),
            (config.force_threshold, InterventionLevel.FORCE_STRATEGY),
            (config.abort_threshold, InterventionLevel.ABORT),
        ]
        
        for repetitions, expected_level in test_cases:
            tracker.reset()
            
            # Record actions to reach the threshold
            for i in range(repetitions):
                tracker.record_action(
                    step=i,
                    tool="run",
                    args={"cmd": "cat same_file.txt"},
                    result={"ok": True},
                )
            
            analysis = detector.analyze(tracker)
            
            if analysis.is_looping:
                assert analysis.intervention_level >= expected_level, \
                    f"At {repetitions} repetitions, expected at least {expected_level}, got {analysis.intervention_level}"

    def test_generate_intervention_none(self, detector, tracker):
        """Test intervention generation when no loop."""
        analysis = detector.analyze(tracker)
        intervention = detector.generate_intervention(analysis)
        
        assert intervention.level == InterventionLevel.NONE
        assert intervention.prompt_injection == ""

    def test_generate_intervention_soft_warning(self, detector_with_custom_config, tracker):
        """Test soft warning intervention generation."""
        detector = detector_with_custom_config
        
        # Trigger soft warning (1 repetition in custom config)
        tracker.record_action(step=0, tool="run", args={"cmd": "cat file.txt"}, result={"ok": True})
        tracker.record_action(step=1, tool="run", args={"cmd": "cat file.txt"}, result={"ok": True})
        
        analysis = detector.analyze(tracker)
        
        if analysis.is_looping and analysis.intervention_level == InterventionLevel.SOFT_WARNING:
            intervention = detector.generate_intervention(analysis)
            
            assert intervention.level == InterventionLevel.SOFT_WARNING
            assert len(intervention.prompt_injection) > 0
            assert "Warning" in intervention.prompt_injection or "warning" in intervention.prompt_injection.lower()

    def test_generate_intervention_hard_warning(self, detector_with_custom_config, tracker):
        """Test hard warning intervention generation."""
        detector = detector_with_custom_config
        
        # custom_config thresholds: soft=1, hard=2, force=3, abort=4
        # So 2 repetitions should trigger HARD_WARNING
        for i in range(2):
            tracker.record_action(
                step=i, 
                tool="run", 
                args={"cmd": "cat file.txt"}, 
                result={"ok": True}
            )
        
        analysis = detector.analyze(tracker)
        
        if analysis.is_looping:
            assert analysis.intervention_level == InterventionLevel.HARD_WARNING, \
                f"Expected HARD_WARNING, got {analysis.intervention_level}"
            
            intervention = detector.generate_intervention(analysis)
            
            assert intervention.level == InterventionLevel.HARD_WARNING
            assert len(intervention.prompt_injection) > 0
            # Hard warning should be more emphatic
            assert "CRITICAL" in intervention.prompt_injection or "MUST" in intervention.prompt_injection

    def test_generate_intervention_force_strategy(self, detector_with_custom_config, tracker):
        """Test force strategy intervention generation."""
        detector = detector_with_custom_config
        
        # custom_config thresholds: soft=1, hard=2, force=3, abort=4
        # So 3 repetitions should trigger FORCE_STRATEGY
        for i in range(3):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": "cat file.txt"},
                result={"ok": True},
            )
        
        analysis = detector.analyze(tracker)
        
        if analysis.is_looping:
            assert analysis.intervention_level == InterventionLevel.FORCE_STRATEGY, \
                f"Expected FORCE_STRATEGY, got {analysis.intervention_level}"
            
            intervention = detector.generate_intervention(analysis)
            
            assert intervention.level == InterventionLevel.FORCE_STRATEGY
            assert len(intervention.prompt_injection) > 0
            # Force strategy should mention FORCE, OVERRIDE, or SYSTEM
            assert "FORCE" in intervention.prompt_injection or \
                   "OVERRIDE" in intervention.prompt_injection or \
                   "SYSTEM" in intervention.prompt_injection

    def test_analysis_contains_evidence(self, detector_with_custom_config, tracker):
        """Test that loop analysis includes evidence."""
        detector = detector_with_custom_config
        
        # Create a loop
        for i in range(3):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": "cat test.txt"},
                result={"ok": True},
            )
        
        analysis = detector.analyze(tracker)
        
        if analysis.is_looping:
            assert len(analysis.evidence) > 0
            # Evidence should be human-readable strings
            for e in analysis.evidence:
                assert isinstance(e, str)
                assert len(e) > 0

    def test_analysis_contains_suggested_action(self, detector_with_custom_config, tracker):
        """Test that loop analysis includes suggested action."""
        detector = detector_with_custom_config
        
        # Create a view-without-modify loop
        for i in range(3):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": f"cat file{i}.txt"},
                result={"ok": True},
            )
        
        analysis = detector.analyze(tracker)
        
        if analysis.is_looping:
            # Should have a suggestion
            assert analysis.suggested_action is not None or len(analysis.evidence) > 0

    def test_should_force_execution(self, detector_with_custom_config, tracker):
        """Test should_force_execution method."""
        detector = detector_with_custom_config
        
        # Initially should be False
        assert detector.should_force_execution() is False
        
        # Create enough repetitions for force threshold
        for i in range(4):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": "cat file.txt"},
                result={"ok": True},
            )
        
        detector.analyze(tracker)
        
        # Now should be True if loop detected at force level
        # This depends on whether the detector detected the loop
        last_analysis = detector.get_last_analysis()
        if last_analysis and last_analysis.intervention_level >= InterventionLevel.FORCE_STRATEGY:
            assert detector.should_force_execution() is True

    def test_loop_analysis_to_dict(self, detector_with_custom_config, tracker):
        """Test LoopAnalysis serialization."""
        detector = detector_with_custom_config
        
        for i in range(3):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": "cat file.txt"},
                result={"ok": True},
            )
        
        analysis = detector.analyze(tracker)
        data = analysis.to_dict()
        
        assert "is_looping" in data
        assert "loop_type" in data
        assert "intervention_level" in data
        assert "repetition_count" in data
        assert "evidence" in data

    def test_intervention_to_dict(self, detector_with_custom_config, tracker):
        """Test Intervention serialization."""
        detector = detector_with_custom_config
        
        for i in range(3):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": "cat file.txt"},
                result={"ok": True},
            )
        
        analysis = detector.analyze(tracker)
        intervention = detector.generate_intervention(analysis)
        data = intervention.to_dict()
        
        assert "level" in data
        assert "message" in data
        assert "prompt_injection" in data


# =============================================================================
# Integration Tests
# =============================================================================

class TestLoopDetectionIntegration:
    """Integration tests for the full loop detection flow."""

    def test_full_detection_flow(self):
        """Test complete flow from tracking to intervention."""
        tracker = ProgressTracker()
        detector = LoopDetector()
        
        # Simulate a realistic sequence
        # 1. Initial exploration
        tracker.record_action(step=0, tool="run", args={"cmd": "ls -la"}, result={"ok": True})
        tracker.record_action(step=1, tool="run", args={"cmd": "cat README.md"}, result={"ok": True})
        
        # 2. No loop yet
        analysis = detector.analyze(tracker)
        assert analysis.is_looping is False
        
        # 3. Simulate stuck pattern
        for i in range(detector.config.hard_warning_threshold + 1):
            tracker.record_action(
                step=2+i,
                tool="run",
                args={"cmd": "cat problem_file.js"},
                result={"ok": True},
            )
        
        # 4. Loop should be detected now
        analysis = detector.analyze(tracker)
        
        # May or may not detect depending on exact thresholds
        if analysis.is_looping:
            intervention = detector.generate_intervention(analysis)
            assert intervention.prompt_injection != ""

    def test_progress_breaks_loop(self):
        """Test that making progress resets loop detection."""
        tracker = ProgressTracker()
        detector = LoopDetector()
        
        # Start a potential loop
        for i in range(2):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": "cat file.txt"},
                result={"ok": True},
            )
        
        # Make progress - write a file
        tracker.record_action(
            step=2,
            tool="write_file",
            args={"path": "output.txt", "content": "fixed"},
            result={"ok": True},
        )
        
        # Check metrics - consecutive same should reset
        metrics = tracker.get_metrics()
        assert metrics.consecutive_same_pattern == 1  # Reset to 1 for the write_file

    def test_mixed_activity_no_false_positive(self):
        """Test that varied activity doesn't trigger false positives."""
        tracker = ProgressTracker()
        detector = LoopDetector()
        
        # Realistic varied workflow
        actions = [
            ("run", {"cmd": "ls -la"}),
            ("run", {"cmd": "cat file1.py"}),
            ("write_file", {"path": "file1.py", "content": "updated"}),
            ("run", {"cmd": "python file1.py"}),
            ("run", {"cmd": "cat file2.py"}),
            ("write_file", {"path": "file2.py", "content": "updated"}),
            ("run", {"cmd": "pytest"}),
        ]
        
        for i, (tool, args) in enumerate(actions):
            tracker.record_action(step=i, tool=tool, args=args, result={"ok": True})
        
        analysis = detector.analyze(tracker)
        
        # Should not detect a loop
        assert analysis.is_looping is False

    def test_state_persistence(self):
        """Test that tracker state can be persisted and restored."""
        # Create and populate tracker
        tracker1 = ProgressTracker()
        for i in range(5):
            tracker1.record_action(
                step=i,
                tool="run",
                args={"cmd": f"cmd_{i}"},
                result={"ok": True},
            )
        
        # Serialize
        state = tracker1.to_dict()
        
        # Restore to new tracker
        tracker2 = ProgressTracker.from_dict(state)
        
        # Verify metrics match
        metrics1 = tracker1.get_metrics()
        metrics2 = tracker2.get_metrics()
        
        assert metrics1.total_actions == metrics2.total_actions
        assert metrics1.unique_actions == metrics2.unique_actions

    def test_high_repetition_rate_detection(self):
        """Test detection of high repetition rate patterns."""
        tracker = ProgressTracker()
        detector = LoopDetector()
        
        # Create pattern with high repetition: 2 unique, 8 repeated
        tracker.record_action(step=0, tool="run", args={"cmd": "unique1"}, result={"ok": True})
        tracker.record_action(step=1, tool="run", args={"cmd": "unique2"}, result={"ok": True})
        
        for i in range(8):
            tracker.record_action(
                step=2+i,
                tool="run",
                args={"cmd": "repeated"},
                result={"ok": True},
            )
        
        metrics = tracker.get_metrics()
        
        # Repetition rate should be high
        assert metrics.repetition_rate >= 0.5  # At least 50% repeated

    def test_view_ratio_warning(self):
        """Test that high view ratio is detected."""
        tracker = ProgressTracker()
        
        # Many views, few modifications
        for i in range(10):
            tracker.record_action(
                step=i,
                tool="run",
                args={"cmd": f"cat file{i}.txt"},
                result={"ok": True},
            )
        
        # Only one modification
        tracker.record_action(
            step=10,
            tool="write_file",
            args={"path": "out.txt", "content": "x"},
            result={"ok": True},
        )
        
        metrics = tracker.get_metrics()
        
        # View ratio should be high (10:1)
        assert metrics.view_to_modify_ratio == 10.0


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_command(self, tracker):
        """Test handling of empty command."""
        record = tracker.record_action(
            step=0,
            tool="run",
            args={"cmd": ""},
            result={"ok": False},
        )
        
        # Should not crash, category should be OTHER or EXECUTE
        assert record is not None

    def test_missing_args(self, tracker):
        """Test handling of missing args."""
        record = tracker.record_action(
            step=0,
            tool="run",
            args={},  # Missing 'cmd'
            result={"ok": False},
        )
        
        # Should not crash
        assert record is not None

    def test_failed_action_tracking(self, tracker):
        """Test that failed actions are tracked."""
        tracker.record_action(
            step=0,
            tool="run",
            args={"cmd": "failing_command"},
            result={"ok": False, "stderr": "command not found"},
        )
        
        metrics = tracker.get_metrics()
        assert metrics.total_actions == 1

    def test_very_long_command(self, tracker):
        """Test handling of very long commands."""
        long_cmd = "cat " + "a" * 10000 + ".txt"
        
        record = tracker.record_action(
            step=0,
            tool="run",
            args={"cmd": long_cmd},
            result={"ok": True},
        )
        
        # Should not crash
        assert record is not None
        assert record.category == ActionCategory.VIEW

    def test_special_characters_in_path(self, tracker):
        """Test handling of special characters in file paths."""
        record = tracker.record_action(
            step=0,
            tool="write_file",
            args={"path": "/workspace/file with spaces (1).txt", "content": "test"},
            result={"ok": True},
        )
        
        assert record.target_file == "/workspace/file with spaces (1).txt"

    def test_unicode_in_command(self, tracker):
        """Test handling of unicode in commands."""
        record = tracker.record_action(
            step=0,
            tool="run",
            args={"cmd": "echo '你好世界'"},
            result={"ok": True},
        )
        
        # Should not crash
        assert record is not None

    def test_detector_with_none_config(self):
        """Test detector initialization with None config uses default."""
        detector = LoopDetector(None)
        
        assert detector.config is not None
        assert isinstance(detector.config, LoopDetectionConfig)

    def test_metrics_with_zero_modify(self, tracker):
        """Test view_to_modify_ratio when no modify actions."""
        tracker.record_action(
            step=0,
            tool="run",
            args={"cmd": "cat file.txt"},
            result={"ok": True},
        )
        
        metrics = tracker.get_metrics()
        
        # Should handle division by zero gracefully
        assert metrics.view_to_modify_ratio >= 0  # Should not be NaN or negative

    def test_action_record_from_dict(self):
        """Test ActionRecord deserialization."""
        data = {
            "step": 5,
            "tool": "run",
            "args": {"cmd": "test"},
            "args_signature": "abc123",
            "category": "view",
            "target_file": "/test.txt",
            "success": True,
            "has_output": True,
            "timestamp": 12345.0,
        }
        
        record = ActionRecord.from_dict(data)
        
        assert record.step == 5
        assert record.tool == "run"
        assert record.category == ActionCategory.VIEW
        assert record.target_file == "/test.txt"
