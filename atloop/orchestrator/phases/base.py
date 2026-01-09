"""Base phase class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

from atloop.orchestrator.state_machine import Phase

if TYPE_CHECKING:
    from atloop.orchestrator.coordinator import WorkflowCoordinator


@dataclass
class PhaseContext:
    """Context for phase execution."""

    step: int
    phase: Phase
    previous_result: Optional[Dict[str, Any]] = None


@dataclass
class PhaseResult:
    """Result of phase execution."""

    success: bool
    data: Dict[str, Any]
    next_phase: Optional[Phase] = None
    error: Optional[str] = None


class BasePhase(ABC):
    """Base class for all phase handlers.

    All phase implementations must inherit from this class
    and implement the execute() method.
    """

    def __init__(self, coordinator: "WorkflowCoordinator"):
        """
        Initialize phase handler.

        Args:
            coordinator: Workflow coordinator instance
        """
        self.coordinator = coordinator

    @abstractmethod
    def execute(self, context: PhaseContext) -> PhaseResult:
        """
        Execute the phase.

        Args:
            context: Phase execution context

        Returns:
            Phase execution result
        """
        pass

    def _transition(self, phase: Phase) -> bool:
        """
        Transition to a new phase.

        Args:
            phase: Target phase

        Returns:
            True if transition is valid
        """
        return self.coordinator.state_machine.transition(phase)
