"""Output handler interface.

Abstract base class for all output handlers.
All output backends (console, HTTP, file, etc.) must implement this interface.
"""

from abc import ABC, abstractmethod

from atloop.output.events import OutputEvent


class OutputHandler(ABC):
    """
    Abstract base class for output handlers.

    All output backends (console, HTTP, file, etc.) must implement this interface.
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize handler.

        Args:
            enabled: Whether handler is enabled
        """
        self.enabled = enabled

    @abstractmethod
    def handle(self, event: OutputEvent) -> None:
        """
        Handle an output event.

        Args:
            event: Event to handle
        """
        pass

    def start(self) -> None:
        """
        Called when handler is activated.
        Override for initialization logic.
        """
        pass

    def stop(self) -> None:
        """
        Called when handler is deactivated.
        Override for cleanup logic.
        """
        pass

    def is_enabled(self) -> bool:
        """Check if handler is enabled."""
        return self.enabled
