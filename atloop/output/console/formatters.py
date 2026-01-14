"""Console formatters for output events.

Formatters convert events into formatted strings for console display.
"""

from abc import ABC, abstractmethod
from typing import Optional, Union
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from atloop.output.events import (
    OutputEvent,
    TaskStartEvent,
    PhaseTransitionEvent,
    ToolCallEvent,
    ToolResultEvent,
    LLMCallEvent,
    LLMStreamEvent,
    LLMResultEvent,
    BudgetUpdateEvent,
    TaskCompleteEvent,
    ErrorEvent,
)


class ConsoleFormatter(ABC):
    """Base class for console formatters."""

    def __init__(self, console: Console):
        """
        Initialize formatter.

        Args:
            console: Rich Console instance
        """
        self.console = console

    @abstractmethod
    def format(self, event: OutputEvent) -> Optional[Union[str, Panel, Text]]:
        """
        Format event for console output.

        Args:
            event: Event to format

        Returns:
            Formatted string or Rich renderable, or None to skip output
        """
        pass


class MinimalConsoleFormatter(ConsoleFormatter):
    """Minimal console formatter - essential information only."""

    def format(self, event: OutputEvent) -> Optional[Union[str, Panel, Text]]:
        """Format event for minimal output."""
        if isinstance(event, TaskStartEvent):
            return self._format_task_start(event)
        elif isinstance(event, PhaseTransitionEvent):
            return self._format_phase_transition(event)
        elif isinstance(event, ToolResultEvent) and not event.success:
            return self._format_tool_failure(event)
        elif isinstance(event, TaskCompleteEvent):
            return self._format_task_complete(event)
        elif isinstance(event, ErrorEvent):
            return self._format_error(event)
        # Skip other events in minimal mode
        return None

    def _format_task_start(self, event: TaskStartEvent) -> Panel:
        """Format task start."""
        content = Text()
        content.append("Task: ", style="bold")
        content.append(event.goal)
        content.append("\nWorkspace: ", style="bold")
        content.append(event.workspace_root)

        return Panel(content, title="atloop", border_style="blue")

    def _format_phase_transition(self, event: PhaseTransitionEvent) -> str:
        """Format phase transition."""
        text = Text()
        text.append(f"[STEP {event.step}] ", style="cyan bold")
        text.append(event.phase, style="yellow bold")
        text.append(" → ")

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

        return str(text)

    def _format_tool_failure(self, event: ToolResultEvent) -> str:
        """Format tool failure."""
        text = Text()
        text.append(f"[STEP {event.step}] ", style="cyan bold")
        text.append("ACT", style="yellow bold")
        text.append(" → Tool failed: ", style="red")
        text.append(event.tool_name, style="red bold")
        if event.error:
            text.append(f"\n  Error: {event.error}", style="red")

        return str(text)

    def _format_task_complete(self, event: TaskCompleteEvent) -> Panel:
        """Format task completion."""
        content = Text()

        # Status
        status_icon = "✓" if event.status == "success" else "✗"
        status_style = "green" if event.status == "success" else "red"
        content.append("Status: ", style="bold")
        content.append(f"{status_icon} {event.status.title()}", style=status_style)

        # Steps
        content.append("\nSteps: ", style="bold")
        content.append(str(event.final_step))

        # Budget
        budget = event.budget_used
        content.append("\nBudget: ", style="bold")
        content.append(f"{budget.get('llm_calls', 0)} LLM calls, ")
        content.append(f"{budget.get('tool_calls', 0)} tool calls, ")
        content.append(f"{budget.get('wall_time_sec', 0)}s")

        title = "Task Complete" if event.status == "success" else "Task Failed"
        return Panel(content, title=title, border_style=status_style)

    def _format_error(self, event: ErrorEvent) -> Panel:
        """Format error."""
        content = Text()
        content.append("Status: ", style="bold")
        content.append("✗ Failure", style="red")
        content.append("\nReason: ", style="bold")
        content.append(event.error_message)
        content.append(f"\nStep: {event.step}", style="bold")

        return Panel(content, title="Task Failed", border_style="red")


class VerboseConsoleFormatter(ConsoleFormatter):
    """Verbose console formatter - comprehensive visibility with full details."""

    def __init__(self, console: Console):
        """Initialize verbose formatter."""
        super().__init__(console)
        self._llm_stream_buffer: str = ""
        self._current_phase: Optional[str] = None

    def format(self, event: OutputEvent) -> Optional[Union[str, Panel, Text]]:
        """Format event for verbose output - shows all events with full details."""
        if isinstance(event, TaskStartEvent):
            return self._format_task_start(event)
        elif isinstance(event, PhaseTransitionEvent):
            return self._format_phase_transition(event)
        elif isinstance(event, ToolCallEvent):
            return self._format_tool_call(event)
        elif isinstance(event, ToolResultEvent):
            return self._format_tool_result(event)
        elif isinstance(event, LLMCallEvent):
            return self._format_llm_call(event)
        elif isinstance(event, LLMStreamEvent):
            return self._format_llm_stream(event)
        elif isinstance(event, LLMResultEvent):
            return self._format_llm_result(event)
        elif isinstance(event, BudgetUpdateEvent):
            return self._format_budget_update(event)
        elif isinstance(event, TaskCompleteEvent):
            return self._format_task_complete(event)
        elif isinstance(event, ErrorEvent):
            return self._format_error(event)
        return None

    def _format_task_start(self, event: TaskStartEvent) -> Panel:
        """Format task start with full details."""
        content = Text()
        content.append("Task ID: ", style="bold")
        content.append(event.task_id)
        content.append("\nGoal: ", style="bold")
        content.append(event.goal)
        content.append("\nWorkspace: ", style="bold")
        content.append(event.workspace_root)
        content.append("\nModel: ", style="bold")
        content.append(event.model)
        content.append("\nBudget: ", style="bold")
        budget = event.budget
        content.append(
            f"{budget.get('max_llm_calls', 0)} LLM calls, "
            f"{budget.get('max_tool_calls', 0)} tool calls, "
            f"{budget.get('max_wall_time_sec', 0)}s"
        )

        return Panel(content, title="atloop", border_style="blue")

    def _format_phase_transition(self, event: PhaseTransitionEvent) -> str:
        """Format phase transition with separator."""
        separator = "=" * 70
        result = f"\n{separator}\n"
        result += f"[STEP {event.step}] {event.phase}\n"
        result += separator

        # Add context if available
        if event.details:
            details = event.details
            if "iteration" in details:
                result += f"\nIteration: {details['iteration']}"
            if "files_found" in details:
                result += f"\n  • Files found: {details['files_found']}"
            if "files_analyzed" in details:
                result += f"\n  • Files analyzed: {details['files_analyzed']}"

        self._current_phase = event.phase
        return result

    def _format_tool_call(self, event: ToolCallEvent) -> Panel:
        """Format tool call with arguments."""
        content = Text()
        content.append(f"[STEP {event.step}] ", style="cyan bold")
        content.append(self._current_phase or "ACT", style="yellow bold")
        content.append(" → Tool: ", style="dim")
        content.append(event.tool_name, style="bold")

        # Format tool arguments
        if event.tool_args:
            content.append("\n\nArguments:", style="bold")
            for key, value in event.tool_args.items():
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 200:
                    value_str = value_str[:200] + "..."
                content.append(f"\n  {key}: ", style="dim")
                content.append(value_str)

        return Panel(content, border_style="dim")

    def _format_tool_result(self, event: ToolResultEvent) -> Panel:
        """Format tool result with full details."""
        content = Text()

        # Status icon
        status_icon = "✓" if event.success else "✗"
        status_style = "green" if event.success else "red"
        content.append(f"{status_icon} ", style=status_style + " bold")
        content.append(event.tool_name, style="bold")

        if event.exit_code is not None:
            content.append(f" (exit code: {event.exit_code})", style="dim")

        if event.duration_ms:
            content.append(f" [{event.duration_ms}ms]", style="dim")

        # Output
        if event.stdout:
            content.append("\n\n┌─ Output ───────────────────────────────────────────┐\n", style="dim")
            # Truncate long output
            stdout = event.stdout
            if len(stdout) > 2000:
                stdout = stdout[:2000] + "\n... (truncated)"
            content.append(stdout)
            content.append("\n└─────────────────────────────────────────────────────┘", style="dim")

        # Error
        if event.error:
            content.append("\n\n┌─ Error ────────────────────────────────────────────┐\n", style="red dim")
            content.append(event.error, style="red")
            content.append("\n└─────────────────────────────────────────────────────┘", style="red dim")

        if event.stderr:
            content.append("\n\n┌─ Stderr ───────────────────────────────────────────┐\n", style="yellow dim")
            stderr = event.stderr
            if len(stderr) > 1000:
                stderr = stderr[:1000] + "\n... (truncated)"
            content.append(stderr, style="yellow")
            content.append("\n└─────────────────────────────────────────────────────┘", style="yellow dim")

        return Panel(content, border_style=status_style)

    def _format_llm_call(self, event: LLMCallEvent) -> Panel:
        """Format LLM call start."""
        content = Text()
        content.append(f"[STEP {event.step}] ", style="cyan bold")
        content.append(self._current_phase or "PLAN", style="yellow bold")
        content.append(" → LLM Call\n", style="dim")
        content.append("Model: ", style="bold")
        content.append(event.model)
        content.append(f"\nPrompt length: {event.prompt_length} chars", style="dim")
        if event.tokens_in:
            content.append(f"\nTokens in: {event.tokens_in}", style="dim")

        return Panel(content, border_style="blue")

    def _format_llm_stream(self, event: LLMStreamEvent) -> Optional[str]:
        """Format LLM stream chunk (accumulate in buffer)."""
        if event.is_complete:
            # Stream complete, buffer will be shown in LLMResultEvent
            self._llm_stream_buffer = ""
            return None
        else:
            # Accumulate chunks
            self._llm_stream_buffer += event.chunk
            # Don't print every chunk, let LLMResultEvent show the full response
            return None

    def _format_llm_result(self, event: LLMResultEvent) -> Panel:
        """Format LLM result with full response."""
        content = Text()
        content.append(f"[STEP {event.step}] ", style="cyan bold")
        content.append(self._current_phase or "PLAN", style="yellow bold")
        content.append(" → LLM Result\n", style="dim")

        content.append("Model: ", style="bold")
        content.append(event.model)
        content.append(f"\nTokens: {event.tokens_in} in / {event.tokens_out} out", style="dim")
        content.append(f"\nDuration: {event.duration_ms}ms", style="dim")

        # Full response
        if event.full_response:
            content.append("\n\n┌─ Response ─────────────────────────────────────────┐\n", style="dim")
            response = event.full_response
            if len(response) > 5000:
                response = response[:5000] + "\n... (truncated)"
            content.append(response)
            content.append("\n└─────────────────────────────────────────────────────┘", style="dim")
        elif self._llm_stream_buffer:
            content.append("\n\n┌─ Response ─────────────────────────────────────────┐\n", style="dim")
            buffer = self._llm_stream_buffer
            if len(buffer) > 5000:
                buffer = buffer[:5000] + "\n... (truncated)"
            content.append(buffer)
            content.append("\n└─────────────────────────────────────────────────────┘", style="dim")
            self._llm_stream_buffer = ""

        # Actions
        if event.actions:
            content.append("\n\nActions:", style="bold")
            for i, action in enumerate(event.actions, 1):
                tool = action.get("tool", "unknown")
                args = action.get("args", {})
                content.append(f"\n  {i}. {tool}: {args}", style="dim")

        content.append(f"\n\nStop reason: {event.stop_reason}", style="dim")

        return Panel(content, border_style="blue")

    def _format_budget_update(self, event: BudgetUpdateEvent) -> str:
        """Format budget update."""
        llm_pct = (event.llm_calls_used / event.llm_calls_max * 100) if event.llm_calls_max > 0 else 0
        tool_pct = (event.tool_calls_used / event.tool_calls_max * 100) if event.tool_calls_max > 0 else 0
        time_pct = (event.wall_time_sec_used / event.wall_time_sec_max * 100) if event.wall_time_sec_max > 0 else 0

        result = "\nBudget Status:\n"
        result += f"  LLM calls: {event.llm_calls_used}/{event.llm_calls_max} ({llm_pct:.0f}%)\n"
        result += f"  Tool calls: {event.tool_calls_used}/{event.tool_calls_max} ({tool_pct:.0f}%)\n"
        result += f"  Wall time: {event.wall_time_sec_used}s/{event.wall_time_sec_max}s ({time_pct:.0f}%)"
        return result

    def _format_task_complete(self, event: TaskCompleteEvent) -> str:
        """Format task completion with comprehensive details."""
        separator = "=" * 70
        result = f"\n{separator}\n"
        result += "[COMPLETE] Task Finished\n"
        result += separator + "\n"

        # Status
        status_icon = "✓" if event.status == "success" else "✗"
        status_style = "green" if event.status == "success" else "red"
        result += f"Status: {status_icon} {event.status.title()}\n"
        result += f"Steps: {event.final_step}\n"
        result += f"Duration: {event.duration_sec}s\n\n"

        # Budget
        result += "Budget Used:\n"
        budget = event.budget_used
        llm_calls = budget.get("llm_calls", 0)
        tool_calls = budget.get("tool_calls", 0)
        wall_time = budget.get("wall_time_sec", 0)
        result += f"  LLM calls: {llm_calls}\n"
        result += f"  Tool calls: {tool_calls}\n"
        result += f"  Wall time: {wall_time}s\n\n"

        # Files modified
        if event.files_modified:
            result += "Files Modified:\n"
            for file in event.files_modified:
                result += f"  • {file}\n"
            result += "\n"

        # Summary
        if event.summary:
            result += f"Summary:\n  {event.summary}\n"

        # Error
        if event.error:
            result += f"\nError: {event.error}\n"

        return result

    def _format_error(self, event: ErrorEvent) -> Panel:
        """Format error with full context."""
        content = Text()
        content.append("Step: ", style="bold")
        content.append(str(event.step))
        content.append("\nPhase: ", style="bold")
        content.append(event.phase)
        content.append("\n\nError Type: ", style="bold")
        content.append(event.error_type, style="red")
        content.append("\nError Message: ", style="bold")
        content.append(event.error_message, style="red")

        if event.error_details:
            content.append("\n\nDetails:", style="bold")
            for key, value in event.error_details.items():
                content.append(f"\n  {key}: ", style="dim")
                value_str = str(value)
                if len(value_str) > 500:
                    value_str = value_str[:500] + "..."
                content.append(value_str, style="dim")

        if event.recoverable:
            content.append("\n\nRecoverable: Yes", style="green")
            if event.recovery_action:
                content.append(f"\nRecovery: {event.recovery_action}", style="green dim")

        return Panel(content, title="Error", border_style="red")
