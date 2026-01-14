"""Console output handler using Rich library."""

from typing import Optional

from rich.console import Console

from atloop.output.console.context import FormatterContext
from atloop.output.console.formatters import (
    ConsoleFormatter,
)
from atloop.output.console.strategy import DebugStrategy, MinimalStrategy, VerboseStrategy
from atloop.output.events import LLMStreamEvent, OutputEvent
from atloop.output.handler import OutputHandler


class ConsoleOutputHandler(OutputHandler):
    """
    Console output handler using Rich library.

    Supports minimal and verbose modes via different formatters.
    """

    def __init__(
        self,
        output_format: str = "minimal",
        enabled: bool = True,
        console: Optional[Console] = None,
        # Deprecated: kept for backward compatibility
        verbose: Optional[bool] = None,
    ):
        """
        Initialize console handler.

        Args:
            output_format: Output format - "minimal", "verbose", or "debug" (default: "minimal")
            enabled: Whether handler is enabled
            console: Rich Console instance (for testing)
            verbose: Deprecated - use output_format="verbose" instead
        """
        super().__init__(enabled=enabled)
        self.console = console or Console()

        # Handle deprecated verbose parameter
        if verbose is not None:
            output_format = "verbose" if verbose else "minimal"

        self.output_format = output_format

        # Create formatter context (shared state)
        self.context = FormatterContext()

        # Use new strategy-based architecture
        # Fallback to old formatters for debug until implemented
        if output_format == "minimal":
            # Use new MinimalStrategy
            self.strategy: Optional[MinimalStrategy] = MinimalStrategy(self.console, self.context)
            self.formatter: Optional[ConsoleFormatter] = None  # Not used in new architecture
        elif output_format == "verbose":
            # Use new VerboseStrategy
            self.strategy: Optional[VerboseStrategy] = VerboseStrategy(self.console, self.context)
            self.formatter: Optional[ConsoleFormatter] = None  # Not used in new architecture
        elif output_format == "debug":
            # Use new DebugStrategy
            self.strategy: Optional[DebugStrategy] = DebugStrategy(self.console, self.context)
            self.formatter: Optional[ConsoleFormatter] = None  # Not used in new architecture
        else:
            # Default to minimal
            self.strategy: Optional[MinimalStrategy] = MinimalStrategy(self.console, self.context)
            self.formatter: Optional[ConsoleFormatter] = None

        self.current_status_line: Optional[str] = None

    def handle(self, event: OutputEvent) -> None:
        """Handle output event."""
        if not self.enabled:
            return

        try:
            # Special handling for LLM streaming in debug mode
            if self.output_format == "debug" and isinstance(event, LLMStreamEvent) and event.chunk:
                # Output LLM stream chunks directly without formatting
                # Use print() instead of console.print() to avoid Rich formatting
                print(event.chunk, end="", flush=True)
                return

            # Use new strategy-based architecture if available
            if self.strategy is not None:
                output = self.strategy.format(event)
                if output:
                    # In debug mode, output may be plain strings
                    if isinstance(output, str):
                        # Use print() for plain strings in debug mode
                        if self.output_format == "debug":
                            print(output)
                        else:
                            self.console.print(output)
                    else:
                        # Rich renderable
                        self.console.print(output)
            # Fallback to old formatter (should not be used in new architecture)
            elif self.formatter is not None:
                output = self.formatter.format(event)
                if output:
                    if isinstance(output, str):
                        self.console.print(output)
                    else:
                        self.console.print(output)
        except Exception as e:
            # Log but don't crash
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Console output error: {e}", exc_info=True)
