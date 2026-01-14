"""Plan entry component for displaying current plan entry with position in minimal mode."""

from typing import Optional
from rich.console import Console, RenderableType
from rich.text import Text

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.context import FormatterContext
from atloop.output.events import OutputEvent, PhaseTransitionEvent


class PlanEntryComponent(FormattingComponent):
    """Formats current plan entry with position indicator for minimal mode.
    
    Only outputs when plan state changes (status or index change).
    Uses different graphic characters for different statuses.
    Format: timestamp [graphic_char] plan_entry [position]
    """

    # Graphic characters for different statuses (no emoji)
    STATUS_CHARS = {
        "completed": "└─",
        "in_progress": "├─",
        "pending": "│ ",
        "failed": "└─",
        "skipped": "└─",
    }

    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """Format plan entry with position - only when state changes.
        
        Args:
            context: Formatter context
            event: PhaseTransitionEvent or LLMResultEvent
        
        Returns:
            Formatted string with plan entry, or None to skip
        """
        # Only handle PhaseTransitionEvent for now
        if not isinstance(event, PhaseTransitionEvent):
            return None
        
        # Check if plan state has changed (only output on change)
        if not context.has_plan_state_changed():
            return None  # No change, skip output
        
        # Get position first to check if there's an active task
        current, total = context.get_plan_position()
        
        # Boundary condition: if current is 0, no active task (all completed or all not started)
        if current == 0:
            return None  # Don't display anything when no active task
        
        # Get plan entry - must have plan to display
        entry = context.get_current_plan_entry()
        if not entry:
            # No plan entry available - don't output anything
            return None
        
        # Get status
        status = context._get_current_plan_status() or "pending"
        
        # Get graphic character based on status
        graphic_char = self.STATUS_CHARS.get(status, "├─")
        
        # Format timestamp
        timestamp = event.timestamp.strftime("%H:%M:%S")
        
        # Build output: timestamp graphic_char entry [current/total]
        output = f"{timestamp} {graphic_char} {entry} [{current}/{total}]"
        
        # Return as Rich Text
        text = Text(output)
        text.stylize("dim", 0, len(timestamp))  # Timestamp in dim
        
        # Style graphic character based on status
        graphic_start = len(timestamp) + 1
        graphic_end = graphic_start + len(graphic_char)
        if status == "completed":
            text.stylize("green", graphic_start, graphic_end)
        elif status == "in_progress":
            text.stylize("cyan", graphic_start, graphic_end)
        elif status == "failed":
            text.stylize("red", graphic_start, graphic_end)
        else:
            text.stylize("dim", graphic_start, graphic_end)
        
        return text
