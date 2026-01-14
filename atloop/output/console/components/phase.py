"""Phase component for displaying phase transitions (used in verbose mode)."""

from typing import Optional
from rich.console import Console, RenderableType
from rich.text import Text

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.context import FormatterContext
from atloop.output.events import OutputEvent, PhaseTransitionEvent


class PhaseComponent(FormattingComponent):
    """Formats phase transitions for verbose mode."""

    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """Format phase transition.
        
        Args:
            context: Formatter context
            event: PhaseTransitionEvent
        
        Returns:
            Rich Text with phase transition, or None to skip
        """
        if not isinstance(event, PhaseTransitionEvent):
            return None
        
        # Build phase transition text
        text = Text()
        text.append(f"[Step {event.step}] ", style="cyan bold")
        text.append(event.phase, style="yellow bold")
        text.append(" → ", style="dim")
        
        # Add context based on phase
        if event.phase == "DISCOVER":
            text.append("Analyzing workspace...", style="dim")
        elif event.phase == "PLAN":
            text.append("Planning actions...", style="dim")
        elif event.phase == "ACT":
            text.append("Executing tools...", style="dim")
        elif event.phase == "VERIFY":
            text.append("Verifying results...", style="dim")
        else:
            text.append("Processing...", style="dim")
        
        return text
