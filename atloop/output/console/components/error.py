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
    """Formats error information using Rich.
    
    Distinguishes between recoverable errors (business-normal, agent loop can handle)
    and fatal errors (true failures that need attention).
    """

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
            Rich Panel with error information, or None to skip (for recoverable errors in minimal mode)
        """
        # Handle ErrorEvent
        if isinstance(event, ErrorEvent):
            # For recoverable errors (business-normal cases like missing placeholders),
            # don't show as red failure in minimal/verbose mode
            # These are expected and agent loop can handle them
            if event.recoverable:
                # Check if error message indicates placeholder/JSON parsing issues
                error_msg_lower = event.error_message.lower()
                is_llm_parsing_issue = any(
                    keyword in error_msg_lower
                    for keyword in [
                        "placeholder",
                        "missing placeholder",
                        "json",
                        "parse",
                        "will retry",
                        "incomplete",
                    ]
                )
                
                # For LLM parsing issues that are recoverable, skip display in minimal/verbose
                # They're logged at debug/info level and don't need red error boxes
                if is_llm_parsing_issue:
                    return None  # Skip display - these are business-normal
            
            # For fatal or non-LLM recoverable errors, show as before
            content = Text()
            if event.recoverable:
                content.append("Status: ", style="bold")
                content.append("⚠ Recoverable", style="yellow bold")
            else:
                content.append("Status: ", style="bold")
                content.append("✗ Failure", style="red bold")
            
            content.append("\nReason: ", style="bold")
            if event.recoverable:
                content.append(event.error_message, style="yellow")
            else:
                content.append(event.error_message, style="red")
            
            content.append(f"\nStep: {event.step}", style="bold")
            content.append(f"\nPhase: {event.phase}", style="bold")

            if event.error_type:
                content.append(f"\nError Type: {event.error_type}", style="dim")

            border_style = "yellow" if event.recoverable else "red"
            title = "Recoverable Error" if event.recoverable else "Task Failed"

            return Panel(
                content,
                title=title,
                border_style=border_style,
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
