"""Error component for displaying error information."""

from typing import Optional

from rich.box import DOUBLE
from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.context import FormatterContext
from atloop.output.events import ErrorEvent, OutputEvent, ToolResultEvent


class ErrorComponent(FormattingComponent):
    """Formats error information using Rich."""

    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """Format error information.

        Args:
            context: Formatter context
            event: ErrorEvent or ToolResultEvent (if failed)

        Returns:
            Rich Panel with error information, or None to skip
        """
        # Handle ErrorEvent
        if isinstance(event, ErrorEvent):
            content = Text()
            content.append("Status: ", style="bold")
            content.append("✗ Failure", style="red bold")
            content.append("\nReason: ", style="bold")
            content.append(event.error_message, style="red")
            content.append(f"\nStep: {event.step}", style="bold")
            content.append(f"\nPhase: {event.phase}", style="bold")

            if event.error_type:
                content.append(f"\nError Type: {event.error_type}", style="dim")

            return Panel(
                content,
                title="Task Failed",
                border_style="red",
                box=DOUBLE,
            )

        # Handle failed ToolResultEvent (for minimal mode - only show failures)
        if isinstance(event, ToolResultEvent) and not event.success:
            content = Text()
            content.append("Tool Failed: ", style="bold")
            content.append(event.tool_name, style="red bold")

            if event.error:
                content.append(f"\nError: {event.error}", style="red")
            elif event.stderr:
                # Show first line of stderr
                stderr_lines = event.stderr.split("\n")
                if stderr_lines:
                    content.append(f"\nError: {stderr_lines[0][:100]}", style="red")

            return Panel(
                content,
                title=f"Tool Error - Step {event.step}",
                border_style="red",
                box=DOUBLE,
            )

        return None
