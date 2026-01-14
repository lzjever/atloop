"""Plan table component for displaying PLAN phase information as Rich table."""

import json
from typing import Any, Dict, Optional

from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.context import FormatterContext
from atloop.output.events import LLMResultEvent, OutputEvent


class PlanTableComponent(FormattingComponent):
    """Formats plan information as Rich table for PLAN phase.

    Extracts and displays:
    - Thinking process (current_step_thoughts)
    - Overall plan (plan items)
    - Current task
    - Planned actions
    """

    def format(
        self,
        context: FormatterContext,
        event: Optional[OutputEvent] = None,
    ) -> Optional[RenderableType]:
        """Format PLAN phase information as table.

        Args:
            context: Formatter context
            event: LLMResultEvent

        Returns:
            Rich Panel with plan table, or None to skip
        """
        if not isinstance(event, LLMResultEvent):
            return None

        # Only format for PLAN phase
        if context.phase != "PLAN":
            return None

        # Extract plan information
        plan_info = self._extract_plan_info(context, event)

        if not plan_info:
            return None

        # Create table
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Field", style="dim", width=20, no_wrap=True)
        table.add_column("Content", width=60)

        # Add rows based on available information
        if plan_info.get("thoughts"):
            thoughts = plan_info["thoughts"]
            # Truncate if too long
            if len(thoughts) > 500:
                thoughts = thoughts[:500] + "..."
            table.add_row("Thinking Process", thoughts)

        if plan_info.get("plan_items"):
            plan_items = plan_info["plan_items"]
            # Format as numbered list
            plan_text = "\n".join(f"  {i + 1}. {item}" for i, item in enumerate(plan_items[:10]))
            if len(plan_items) > 10:
                plan_text += f"\n  ... ({len(plan_items)} items total)"
            table.add_row("Overall Plan", plan_text)

        if plan_info.get("current_task"):
            table.add_row("Current Task", plan_info["current_task"])

        if plan_info.get("planned_actions"):
            actions_text = "\n".join(f"  • {action}" for action in plan_info["planned_actions"])
            table.add_row("Planned Actions", actions_text)

        # If table is empty, skip
        if len(table.rows) == 0:
            return None

        # Wrap in panel (use default box, table doesn't need special box)
        return Panel(
            table,
            title=f"PLAN Phase - Step {event.step}",
            border_style="blue",
        )

    def _extract_plan_info(
        self, context: FormatterContext, event: LLMResultEvent
    ) -> Dict[str, Any]:
        """Extract plan information from multiple sources.

        Tries:
        1. Parse from full_response JSON
        2. Use context.plan if available
        3. Extract from actions

        Args:
            context: Formatter context
            event: LLM result event

        Returns:
            Dictionary with plan information
        """
        plan_info: Dict[str, Any] = {}

        # Try to parse from full_response JSON
        if event.full_response:
            try:
                data = json.loads(event.full_response)

                # Extract current_step_thoughts
                if "current_step_thoughts" in data:
                    plan_info["thoughts"] = data["current_step_thoughts"]

                # Extract plan
                if "plan" in data and data["plan"]:
                    plan_data = data["plan"]
                    if isinstance(plan_data, list):
                        plan_info["plan_items"] = [str(item) for item in plan_data]
                    elif isinstance(plan_data, str):
                        # Split by newlines
                        plan_info["plan_items"] = [
                            line.strip()
                            for line in plan_data.split("\n")
                            if line.strip() and not line.strip().startswith("#")
                        ]
            except (json.JSONDecodeError, KeyError):
                # Fallback to other sources
                pass

        # Use context.plan if available and not already extracted
        if "plan_items" not in plan_info and context.plan:
            plan_items = []
            for step in context.plan:
                if hasattr(step, "description"):
                    plan_items.append(step.description)
                elif isinstance(step, dict):
                    plan_items.append(step.get("description", step.get("id", "")))
                else:
                    plan_items.append(str(step))
            if plan_items:
                plan_info["plan_items"] = plan_items

        # Extract current task - use plan_state for efficient query
        current_entry = context.get_current_plan_entry()
        if current_entry:
            current, total = context.get_plan_position()
            if current > 0:
                plan_info["current_task"] = f"{current_entry} ({current}/{total})"
            # If current is 0, no active task (all completed or all not started)

        # Extract planned actions from event.actions
        if event.actions:
            planned_actions = []
            for action in event.actions:
                tool = action.get("tool", "")
                args = action.get("args", {})

                if tool == "run" and "cmd" in args:
                    planned_actions.append(f"Execute command: {args['cmd']}")
                elif tool == "write_file" and "path" in args:
                    planned_actions.append(f"Write file: {args['path']}")
                elif tool == "read_file" and "path" in args:
                    planned_actions.append(f"Read file: {args['path']}")
                elif tool == "edit_file" and "path" in args:
                    planned_actions.append(f"Edit file: {args['path']}")
                else:
                    planned_actions.append(f"{tool}: {args}")

            if planned_actions:
                plan_info["planned_actions"] = planned_actions

        return plan_info
