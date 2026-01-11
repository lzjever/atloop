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
    """Result of phase execution.
    
    Design principles:
    - Phase is responsible for setting state.last_error.summary (the authoritative source)
    - PhaseResult.error is only for logging, debugging, and error classification
    - Workflow should trust Phase's state and not overwrite it
    """

    success: bool
    data: Dict[str, Any]
    next_phase: Optional[Phase] = None
    error: Optional[str] = None  # Error message for logging/classification, NOT for updating state
    recoverable: bool = False  # Whether the error is recoverable (for error handling)
    error_already_set_in_state: bool = False  # If True, Phase has already set detailed error in state.last_error.summary


class BasePhase(ABC):
    """Base class for all phase handlers.

    All phase implementations must inherit from this class
    and implement the execute() method.

    **Error Handling Guidelines:**
    
    When a Phase encounters an error that should be reported to the LLM:
    
    1. **Set detailed error info in state.last_error.summary**:
       - Include tool name, command (if applicable), stdout, stderr
       - This is the authoritative source of error information for LLM
       - Format should be comprehensive and structured
    
    2. **Return PhaseResult with error_already_set_in_state=True**:
       - Only if you've set detailed error info in state.last_error.summary
       - This tells Workflow to trust your state and not overwrite it
       - PhaseResult.error should be a brief summary for logging/classification only
    
    3. **For non-fatal errors (recoverable=True)**:
       - Set error info in state
       - Return PhaseResult with recoverable=True and error_already_set_in_state=True
       - Workflow will transition to PLAN phase for LLM to adjust strategy
    
    4. **For fatal errors (recoverable=False)**:
       - Set error info in state
       - Return PhaseResult with recoverable=False
       - Workflow will transition to FAIL phase
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
            
        Note:
            If you set detailed error info in state.last_error.summary,
            make sure to set error_already_set_in_state=True in the returned PhaseResult.
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
