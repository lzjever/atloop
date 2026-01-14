"""Raw event component for displaying events as plain text (debug mode).

This component outputs events as raw strings without any Rich formatting,
making it suitable for programmatic analysis and logging.
"""

from typing import Optional
from rich.console import Console, RenderableType

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.context import FormatterContext
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


class RawEventComponent(FormattingComponent):
    """Formats events as raw text strings for debug mode.
    
    Outputs events in a simple, parseable format without Rich formatting.
    This makes the output suitable for:
    - Programmatic analysis
    - Log file parsing
    - Debugging and troubleshooting
    """

    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """Format event as raw text string.
        
        Args:
            context: Formatter context
            event: Output event
        
        Returns:
            Plain string representation of event, or None to skip
        """
        if event is None:
            return None
        
        # Format timestamp
        timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        # Build event string
        event_str = f"[{timestamp}] {event.event_type.value.upper()}"
        event_str += f" step={event.step} task_id={event.task_id}"
        
        # Add event-specific fields
        if isinstance(event, TaskStartEvent):
            event_str += f" goal={event.goal[:50]}..."
            event_str += f" session_id={event.session_id or 'None'}"
            event_str += f" runs_dir={event.runs_dir}"
        
        elif isinstance(event, PhaseTransitionEvent):
            event_str += f" phase={event.phase}"
            if event.previous_phase:
                event_str += f" previous_phase={event.previous_phase}"
        
        elif isinstance(event, ToolCallEvent):
            event_str += f" tool={event.tool_name}"
            event_str += f" tool_id={event.tool_id or 'None'}"
            # Format args (truncate if too long)
            args_str = str(event.tool_args)
            if len(args_str) > 100:
                args_str = args_str[:100] + "..."
            event_str += f" args={args_str}"
        
        elif isinstance(event, ToolResultEvent):
            event_str += f" tool={event.tool_name}"
            event_str += f" tool_id={event.tool_id or 'None'}"
            event_str += f" success={event.success}"
            if event.exit_code is not None:
                event_str += f" exit_code={event.exit_code}"
            if event.duration_ms:
                event_str += f" duration_ms={event.duration_ms}"
            if event.error:
                error_preview = event.error[:100] + "..." if len(event.error) > 100 else event.error
                event_str += f" error={error_preview}"
            if event.stdout:
                stdout_preview = event.stdout[:100] + "..." if len(event.stdout) > 100 else event.stdout
                event_str += f" stdout_len={len(event.stdout)} stdout_preview={stdout_preview}"
        
        elif isinstance(event, LLMCallEvent):
            event_str += f" model={event.model}"
            event_str += f" prompt_length={event.prompt_length}"
            if event.tokens_in:
                event_str += f" tokens_in={event.tokens_in}"
        
        elif isinstance(event, LLMStreamEvent):
            # For streaming, output chunk directly (handled separately)
            # This component will return None for stream events
            return None
        
        elif isinstance(event, LLMResultEvent):
            event_str += f" model={event.model}"
            event_str += f" tokens_in={event.tokens_in} tokens_out={event.tokens_out}"
            event_str += f" actions_count={len(event.actions)}"
            event_str += f" stop_reason={event.stop_reason}"
            event_str += f" duration_ms={event.duration_ms}"
            if event.full_response:
                event_str += f" full_response_len={len(event.full_response)}"
        
        elif isinstance(event, BudgetUpdateEvent):
            event_str += f" llm_calls={event.llm_calls_used}/{event.llm_calls_max}"
            event_str += f" tool_calls={event.tool_calls_used}/{event.tool_calls_max}"
            event_str += f" wall_time={event.wall_time_sec_used}/{event.wall_time_sec_max}s"
        
        elif isinstance(event, TaskCompleteEvent):
            event_str += f" status={event.status}"
            event_str += f" final_step={event.final_step}"
            event_str += f" duration_sec={event.duration_sec}"
            event_str += f" session_id={event.session_id or 'None'}"
            event_str += f" runs_dir={event.runs_dir}"
        
        elif isinstance(event, ErrorEvent):
            event_str += f" phase={event.phase}"
            event_str += f" error_type={event.error_type}"
            error_preview = event.error_message[:100] + "..." if len(event.error_message) > 100 else event.error_message
            event_str += f" error_message={error_preview}"
            event_str += f" recoverable={event.recoverable}"
        
        # Return as plain string (not Rich renderable)
        return event_str
