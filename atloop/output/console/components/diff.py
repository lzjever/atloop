"""Diff component for displaying file diffs with syntax highlighting."""

from typing import Optional
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.text import Text

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.context import FormatterContext
from atloop.output.events import OutputEvent


class DiffComponent(FormattingComponent):
    """Formats file diff with syntax highlighting using Rich.
    
    Parses unified diff format and displays with color coding:
    - Green for added lines (+)
    - Red for removed lines (-)
    - Cyan for diff headers (@@)
    - Dim for context lines
    """

    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """Format diff from context.
        
        This method is not typically called directly.
        Use format_diff() instead.
        
        Args:
            context: Formatter context
            event: Optional event
        
        Returns:
            None (use format_diff() instead)
        """
        return None

    def format_diff(self, diff_text: str, file_path: str) -> Optional[Panel]:
        """Format unified diff text with syntax highlighting.
        
        Args:
            diff_text: Unified diff text
            file_path: Path of the file being diffed
        
        Returns:
            Rich Panel with formatted diff, or None if diff is empty
        """
        if not diff_text or not diff_text.strip():
            return None
        
        # Parse unified diff line by line
        diff_lines = diff_text.splitlines()
        
        # Build Rich Text with color coding
        text = Text()
        for line in diff_lines:
            if line.startswith("+++"):
                # File header
                text.append(line + "\n", style="cyan bold")
            elif line.startswith("---"):
                # File header
                text.append(line + "\n", style="cyan bold")
            elif line.startswith("@@"):
                # Hunk header
                text.append(line + "\n", style="cyan bold")
            elif line.startswith("+"):
                # Added line
                text.append(line + "\n", style="green")
            elif line.startswith("-"):
                # Removed line
                text.append(line + "\n", style="red")
            else:
                # Context line
                text.append(line + "\n", style="dim")
        
        # Truncate if too long (limit to ~100 lines for display)
        if len(diff_lines) > 100:
            # Keep first 50 and last 50 lines
            text_lines = text.split("\n")
            truncated = Text()
            truncated.append("\n".join(str(text_lines[i]) for i in range(50)))
            truncated.append("\n... (omitted middle part) ...\n", style="dim")
            truncated.append("\n".join(str(text_lines[i]) for i in range(len(text_lines) - 50, len(text_lines))))
            text = truncated
        
        # Create panel
        return Panel(
            text,
            title=f"Changes: {file_path}",
            border_style="yellow",
        )
