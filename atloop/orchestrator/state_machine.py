"""State machine for agent execution phases."""

from enum import Enum


class Phase(Enum):
    """Agent execution phases."""

    DISCOVER = "DISCOVER"
    PLAN = "PLAN"
    ACT = "ACT"
    VERIFY = "VERIFY"
    DONE = "DONE"
    FAIL = "FAIL"

    @classmethod
    def from_string(cls, phase_str: str) -> "Phase":
        """Create from string."""
        try:
            return cls(phase_str.upper())
        except ValueError:
            return cls.DISCOVER

    def __str__(self) -> str:
        """String representation."""
        return self.value


class StateMachine:
    """State machine for agent execution."""

    def __init__(self):
        """Initialize state machine."""
        self.current_phase = Phase.DISCOVER

    def transition(self, phase: Phase) -> bool:
        """
        Transition to a new phase.

        Args:
            phase: Target phase

        Returns:
            True if transition is valid
        """
        # Define valid transitions
        valid_transitions = {
            Phase.DISCOVER: [Phase.PLAN, Phase.FAIL],
            Phase.PLAN: [
                Phase.ACT,
                Phase.DONE,
                Phase.FAIL,
            ],  # Allow PLAN -> DONE when LLM decides task is done
            Phase.ACT: [Phase.VERIFY, Phase.FAIL],
            Phase.VERIFY: [Phase.DONE, Phase.DISCOVER, Phase.FAIL],
            Phase.DONE: [],  # Terminal state
            Phase.FAIL: [],  # Terminal state
        }

        if phase in valid_transitions.get(self.current_phase, []):
            self.current_phase = phase
            return True

        # Allow staying in same phase for retries
        if phase == self.current_phase:
            return True

        return False

    def is_terminal(self) -> bool:
        """Check if current phase is terminal."""
        return self.current_phase in [Phase.DONE, Phase.FAIL]

    def reset(self):
        """Reset to initial state."""
        self.current_phase = Phase.DISCOVER
