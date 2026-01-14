"""Action table component for displaying each action as Rich table."""

from typing import Dict, Optional
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.console import Group

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.components.diff import DiffComponent
from atloop.output.console.context import FormatterContext
from atloop.output.events import OutputEvent, ToolCallEvent, ToolResultEvent


class ActionTableComponent(FormattingComponent):
    """Formats each action (tool call + result) as Rich table.
    
    Tracks tool calls and matches them with results to create
    comprehensive action tables.
    """

    def __init__(self, console: Console):
        """Initialize action table component.
        
        Args:
            console: Rich Console instance
        """
        super().__init__(console)
        self._pending_tool_calls: Dict[str, ToolCallEvent] = {}
        self._diff_component = DiffComponent(console)

    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """Format action as table.
        
        Args:
            context: Formatter context
            event: ToolCallEvent or ToolResultEvent
        
        Returns:
            Rich Panel with action table, or None to skip
        """
        # Store tool call for later matching
        if isinstance(event, ToolCallEvent):
            if event.tool_id:
                self._pending_tool_calls[event.tool_id] = event
            return None  # Don't display until result
        
        # Format tool result
        if not isinstance(event, ToolResultEvent):
            return None
        
        # Match with tool call
        tool_call = None
        if event.tool_id and event.tool_id in self._pending_tool_calls:
            tool_call = self._pending_tool_calls.pop(event.tool_id)
        
        # Get diff if file operation
        diff = None
        if event.tool_name in ["write_file", "edit_file", "append_file"]:
            diff = context.current_diff
        
        # Format as table
        return self._format_action_table(tool_call, event, diff)

    def _format_action_table(
        self,
        tool_call: Optional[ToolCallEvent],
        tool_result: ToolResultEvent,
        diff: Optional[str],
    ) -> Panel:
        """Format action as Rich table.
        
        Args:
            tool_call: Optional tool call event
            tool_result: Tool result event
            diff: Optional diff string for file operations
        
        Returns:
            Rich Panel with action information
        """
        # Create table
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="bold", width=15, no_wrap=True)
        table.add_column("Value", width=55)
        
        # Tool name
        table.add_row("Tool", tool_result.tool_name)
        
        # Arguments
        if tool_call:
            args_str = self._format_args(tool_call.tool_args)
            table.add_row("Arguments", args_str)
        elif tool_result.tool_name:
            # Try to infer from tool name
            table.add_row("Arguments", "(None)")
        
        # Status
        status_icon = "✓" if tool_result.success else "✗"
        status_text = f"{status_icon} {'Success' if tool_result.success else 'Failed'}"
        if tool_result.exit_code is not None:
            status_text += f" (exit code: {tool_result.exit_code})"
        table.add_row("Status", status_text)
        
        # Duration
        if tool_result.duration_ms:
            table.add_row("Duration", f"{tool_result.duration_ms}ms")
        
        # Output (stdout)
        if tool_result.stdout:
            stdout_preview = (
                tool_result.stdout[:200] + "..."
                if len(tool_result.stdout) > 200
                else tool_result.stdout
            )
            table.add_row("Output", stdout_preview)
        
        # Error
        if tool_result.error:
            table.add_row("Error", tool_result.error)
        elif tool_result.stderr and not tool_result.success:
            # Show stderr if there's an error
            stderr_preview = (
                tool_result.stderr[:200] + "..."
                if len(tool_result.stderr) > 200
                else tool_result.stderr
            )
            table.add_row("Error", stderr_preview)
        
        # Combine with diff if available
        content_items = [table]
        
        if diff and tool_result.tool_name in ["write_file", "edit_file", "append_file"]:
            # Get file path from tool call or result
            file_path = ""
            if tool_call and "path" in tool_call.tool_args:
                file_path = tool_call.tool_args["path"]
            elif "path" in getattr(tool_result, "tool_args", {}):
                file_path = tool_result.tool_args["path"]  # type: ignore
            
            diff_panel = self._diff_component.format_diff(diff, file_path)
            if diff_panel:
                content_items.append(diff_panel)
        
        # Create panel with appropriate border color
        border_style = "green" if tool_result.success else "red"
        title = f"Action: {tool_result.tool_name}"
        
        if len(content_items) > 1:
            # Multiple items - use Group
            return Panel(
                Group(*content_items),
                title=title,
                border_style=border_style,
            )
        else:
            # Single table
            return Panel(
                table,
                title=title,
                border_style=border_style,
            )

    def _format_args(self, args: Dict[str, any]) -> str:
        """Format tool arguments in human-readable format.
        
        Args:
            args: Tool arguments dictionary
        
        Returns:
            Formatted string
        """
        if "cmd" in args:
            return f"Command: {args['cmd']}"
        elif "path" in args:
            return f"Path: {args['path']}"
        elif len(args) == 0:
            return "(No arguments)"
        else:
            # Format as key=value pairs
            parts = []
            for key, value in args.items():
                if isinstance(value, str) and len(value) > 50:
                    parts.append(f"{key}={value[:50]}...")
                else:
                    parts.append(f"{key}={value}")
            return ", ".join(parts)
