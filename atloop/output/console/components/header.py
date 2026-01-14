"""Header component for displaying task start information with runs directory."""

from typing import Optional
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.text import Text
from rich.box import DOUBLE

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.context import FormatterContext
from atloop.output.events import OutputEvent, TaskStartEvent


class HeaderComponent(FormattingComponent):
    """Formats task start header with runs directory information using Rich."""

    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """Format task start header.
        
        Args:
            context: Formatter context
            event: TaskStartEvent
        
        Returns:
            Rich Panel with header information, or None to skip
        """
        if not isinstance(event, TaskStartEvent):
            return None
        
        # Build content using Rich Text
        content = Text()
        
        # Session ID
        content.append("Session ID: ", style="bold")
        session_display = context.session_id or context.task_id or event.task_id
        content.append(session_display, style="cyan")
        content.append("\n")
        
        # Runs Directory
        content.append("Runs Directory: ", style="bold")
        runs_dir = context.runs_dir or event.runs_dir
        content.append(runs_dir, style="cyan")
        content.append("\n")
        
        # Start Time
        content.append("Start Time: ", style="bold")
        start_time = context.start_time or event.start_time
        if start_time:
            time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            content.append(time_str, style="green")
        else:
            content.append("N/A", style="dim")
        
        # Create panel with box-drawing characters (no emoji)
        return Panel(
            content,
            title="atloop - Task Execution",
            border_style="blue",
            box=DOUBLE,  # Use double-line box
        )
