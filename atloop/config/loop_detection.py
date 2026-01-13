"""
Loop detection and intervention configuration.

This module contains all configuration parameters for detecting execution loops
and triggering interventions when the LLM gets stuck in repetitive patterns.

Design Philosophy:
- Graduated intervention: Warning → Hard Warning → Force Strategy → Abort
- Evidence-based: Actions are compared by their signature, not just tool name
- Configurable thresholds for different use cases
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List


class InterventionLevel(IntEnum):
    """Intervention levels for loop detection.

    Levels are ordered by severity. Higher levels indicate more severe intervention.
    """

    NONE = 0  # Normal operation, no intervention needed
    SOFT_WARNING = 1  # Soft warning added to prompt
    HARD_WARNING = 2  # Hard warning with strong language
    FORCE_STRATEGY = 3  # Force execution of recovery strategy
    ABORT = 4  # Abort current direction, force new approach


@dataclass
class LoopDetectionConfig:
    """Configuration for loop detection and intervention.

    Thresholds:
    - soft_warning_threshold: After N repetitions, add soft warning
    - hard_warning_threshold: After N repetitions, add hard warning
    - force_threshold: After N repetitions, force recovery strategy
    - abort_threshold: After N repetitions, abort and force new direction

    A "repetition" is defined as executing the same action pattern
    (same tool + similar args) without making progress.
    """

    # === Repetition Thresholds ===
    # How many repeated action patterns before each intervention level
    soft_warning_threshold: int = 2  # After 2 repetitions → soft warning
    hard_warning_threshold: int = 3  # After 3 repetitions → hard warning
    force_threshold: int = 5  # After 5 repetitions → force recovery
    abort_threshold: int = 8  # After 8 repetitions → abort direction

    # === Pattern Detection Settings ===
    # Window size for detecting patterns (how many recent steps to analyze)
    pattern_window_size: int = 10

    # Similarity threshold for considering two actions as "same" (0-1)
    # 1.0 = exact match, 0.8 = 80% similar
    action_similarity_threshold: float = 0.8

    # === View Without Fix Detection ===
    # Maximum allowed view operations without a modify operation
    max_view_without_modify: int = 3

    # Commands considered as "view" operations
    view_commands: List[str] = field(
        default_factory=lambda: ["cat", "head", "tail", "less", "more", "grep", "find", "ls", "wc"]
    )

    # Tools considered as "modify" operations
    modify_tools: List[str] = field(
        default_factory=lambda: ["write_file", "edit_file", "append_file", "multi_edit_file"]
    )

    # === Recovery Strategy Settings ===
    # When force_threshold is reached, these actions are suggested/forced
    recovery_strategies: List[str] = field(
        default_factory=lambda: [
            "execute_to_verify",  # Run the script/code to get actual errors
            "change_approach",  # Suggest a different approach
            "simplify_task",  # Break task into smaller steps
        ]
    )

    # === Progress Metrics Settings ===
    # Minimum progress required to reset repetition counter
    min_progress_to_reset: int = 1  # At least 1 new unique action

    # Progress metrics weights for scoring
    weight_files_created: float = 3.0
    weight_files_modified: float = 2.0
    weight_commands_executed: float = 0.5
    weight_unique_actions: float = 1.0

    def get_intervention_level(self, repetition_count: int) -> InterventionLevel:
        """Determine intervention level based on repetition count."""
        if repetition_count >= self.abort_threshold:
            return InterventionLevel.ABORT
        elif repetition_count >= self.force_threshold:
            return InterventionLevel.FORCE_STRATEGY
        elif repetition_count >= self.hard_warning_threshold:
            return InterventionLevel.HARD_WARNING
        elif repetition_count >= self.soft_warning_threshold:
            return InterventionLevel.SOFT_WARNING
        else:
            return InterventionLevel.NONE


# Default configuration instance
DEFAULT_LOOP_DETECTION_CONFIG = LoopDetectionConfig()
