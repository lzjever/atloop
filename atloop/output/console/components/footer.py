"""Footer component for displaying task completion information."""

from typing import Optional
from rich.console import Console, RenderableType
from rich.text import Text

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.context import FormatterContext
from atloop.output.events import OutputEvent, TaskCompleteEvent


class FooterComponent(FormattingComponent):
    """Formats task completion footer with duration, end time, file changes, and result message."""

    # Suffix for result message (for programmatic parsing)
    RESULT_MESSAGE_SUFFIX = "ATLOOP_RESULT_MESSAGE:"

    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """Format task completion footer.
        
        Format:
        - Duration: X.Xs
        - End Time: YYYY-MM-DD HH:MM:SS
        - Files modified: [list of files]
        - ATLOOP_RESULT_MESSAGE: [summary on new line]
        
        Args:
            context: Formatter context
            event: TaskCompleteEvent
        
        Returns:
            Rich Text with footer information, or None to skip
        """
        if not isinstance(event, TaskCompleteEvent):
            return None
        
        # Calculate duration
        end_time = context.end_time or event.end_time
        start_time = context.start_time or event.start_time
        
        duration_sec = 0.0
        if end_time and start_time:
            duration_sec = (end_time - start_time).total_seconds()
        elif event.duration_sec:
            duration_sec = event.duration_sec
        
        # Build content using Rich Text (plain text, no panel)
        content = Text()
        
        # Duration
        content.append("Duration: ", style="bold")
        duration_str = f"{duration_sec:.1f}s"
        content.append(duration_str, style="green")
        content.append("\n")
        
        # End Time
        content.append("End Time: ", style="bold")
        if end_time:
            time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
            content.append(time_str, style="green")
        else:
            content.append("N/A", style="dim")
        content.append("\n")
        
        # Files modified (created + modified)
        if event.files_modified:
            content.append("Files modified: ", style="bold")
            files_str = ", ".join(event.files_modified)
            content.append(files_str, style="cyan")
            content.append("\n")
        
        # Result message (with explicit suffix for programmatic parsing)
        if event.summary:
            content.append("\n")  # Empty line before result message
            content.append(self.RESULT_MESSAGE_SUFFIX, style="bold yellow")
            content.append("\n")  # New line after suffix
            content.append(event.summary, style="white")
        
        return content
