"""Base class for formatting components.

Formatting components are reusable, stateless formatters that convert
events and context into Rich renderables. They follow the single
responsibility principle - each component formats one specific type of data.
"""

from abc import ABC, abstractmethod
from typing import Optional

from rich.console import Console, RenderableType

from atloop.output.console.context import FormatterContext
from atloop.output.events import OutputEvent


class FormattingComponent(ABC):
    """Abstract base class for formatting components.

    Formatting components are stateless, pure functions that format
    data based on context and events. They can be composed by strategies
    to create different output formats.
    """

    def __init__(self, console: Console):
        """
        Initialize formatting component.

        Args:
            console: Rich Console instance for rendering
        """
        self.console = console

    @abstractmethod
    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """
        Format data into Rich renderable.

        Args:
            context: Formatter context with current state
            event: Optional event that triggered formatting

        Returns:
            Rich renderable (Panel, Text, Table, etc.) or None to skip output
        """
        pass

    def can_format(self, context: FormatterContext, event: Optional[OutputEvent]) -> bool:
        """Check if this component can format given context/event.

        Override this method to provide custom filtering logic.
        By default, returns True (component will attempt to format).

        Args:
            context: Formatter context
            event: Optional event

        Returns:
            True if component can format, False otherwise
        """
        return True
