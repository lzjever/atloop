"""Memory dump component for displaying memory information in debug mode."""

from typing import Any, Optional
from rich.console import Console, RenderableType

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.context import FormatterContext
from atloop.output.events import OutputEvent, PhaseTransitionEvent


class MemoryDumpComponent(FormattingComponent):
    """Formats memory information as plain text for debug mode.
    
    Displays key memory statistics and plan information
    after each phase transition.
    """

    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """Format memory dump.
        
        Args:
            context: Formatter context
            event: PhaseTransitionEvent (triggers memory dump)
        
        Returns:
            Plain string with memory information, or None to skip
        """
        # Only dump memory on phase transitions
        if not isinstance(event, PhaseTransitionEvent):
            return None
        
        # Build memory dump string
        lines = []
        lines.append("\n=== Memory Dump ===")
        lines.append(f"Phase: {context.phase or 'None'}")
        lines.append(f"Step: {context.step}")
        
        # Plan information
        if context.plan:
            current, total = context.get_plan_position()
            if current > 0:
                lines.append(f"Plan: {len(context.plan)} items (current: {current}/{total})")
            else:
                # No active task (all completed or all not started)
                lines.append(f"Plan: {len(context.plan)} items (no active task)")
            
            # Show plan items (limit to 10)
            for i, step in enumerate(context.plan[:10]):
                if hasattr(step, "status") and hasattr(step, "description"):
                    # PlanStep object
                    lines.append(f"  {i+1}. [{step.status}] {step.description}")
                elif isinstance(step, dict):
                    # Dict format
                    status = step.get("status", "unknown")
                    description = step.get("description", step.get("id", "Unknown"))
                    lines.append(f"  {i+1}. [{status}] {description}")
                else:
                    # String format
                    lines.append(f"  {i+1}. {step}")
            
            if len(context.plan) > 10:
                lines.append(f"  ... ({len(context.plan)} items total, showing first 10)")
        else:
            lines.append("Plan: No plan available")
        
        # Session info
        if context.session_id:
            lines.append(f"Session ID: {context.session_id}")
        if context.runs_dir:
            lines.append(f"Runs Directory: {context.runs_dir}")
        
        # Diff info
        if context.current_diff:
            diff_lines = len(context.current_diff.splitlines())
            lines.append(f"Current Diff: {diff_lines} lines")
        else:
            lines.append("Current Diff: None")
        
        # LLM response cache
        if context.last_llm_response:
            lines.append(f"Last LLM Response: step={context.last_llm_response.get('step', 'unknown')}")
            if context.last_llm_response.get("actions"):
                lines.append(f"  Actions: {len(context.last_llm_response['actions'])}")
        
        lines.append("==================\n")
        
        # Return as plain string
        return "\n".join(lines)
