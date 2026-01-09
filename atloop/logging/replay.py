"""Replay functionality for agent execution."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class EventReplay:
    """Replay agent execution from events.jsonl."""

    def __init__(self, events_file: Path):
        """
        Initialize event replay.

        Args:
            events_file: Path to events.jsonl file
        """
        self.events_file = Path(events_file)
        if not self.events_file.exists():
            raise FileNotFoundError(f"Events file not found: {events_file}")

        self.events: List[Dict[str, Any]] = []
        self._load_events()

    def _load_events(self):
        """Load events from JSONL file."""
        with open(self.events_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        event = json.loads(line)
                        self.events.append(event)
                    except json.JSONDecodeError:
                        continue  # Skip invalid lines

    def get_events_by_step(self, step: int) -> List[Dict[str, Any]]:
        """
        Get all events for a specific step.

        Args:
            step: Step number

        Returns:
            List of events for the step
        """
        return [e for e in self.events if e.get("step") == step]

    def get_events_up_to_step(self, step: int) -> List[Dict[str, Any]]:
        """
        Get all events up to and including a specific step.

        Args:
            step: Step number

        Returns:
            List of events up to the step
        """
        return [e for e in self.events if e.get("step", 0) <= step]

    def get_tool_calls(self, step: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all tool call events.

        Args:
            step: Optional step filter

        Returns:
            List of tool call events
        """
        events = self.events if step is None else self.get_events_by_step(step)
        return [e for e in events if e.get("t") == "tool_call"]

    def get_tool_results(self, step: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all tool result events.

        Args:
            step: Optional step filter

        Returns:
            List of tool result events
        """
        events = self.events if step is None else self.get_events_by_step(step)
        return [e for e in events if e.get("t") == "tool_result"]

    def get_llm_calls(self, step: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all LLM call events.

        Args:
            step: Optional step filter

        Returns:
            List of LLM call events
        """
        events = self.events if step is None else self.get_events_by_step(step)
        return [e for e in events if e.get("t") == "llm_call"]

    def get_llm_results(self, step: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all LLM result events.

        Args:
            step: Optional step filter

        Returns:
            List of LLM result events
        """
        events = self.events if step is None else self.get_events_by_step(step)
        return [e for e in events if e.get("t") == "llm_result"]

    def get_state_changes(self, step: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all state change events.

        Args:
            step: Optional step filter

        Returns:
            List of state change events
        """
        events = self.events if step is None else self.get_events_by_step(step)
        return [e for e in events if e.get("t") == "state_change"]

    def get_final_state(self) -> Optional[Dict[str, Any]]:
        """
        Get the final state from events.

        Returns:
            Final state dictionary or None
        """
        state_changes = self.get_state_changes()
        if not state_changes:
            return None

        # Get the last state change
        final_state = state_changes[-1]
        return {
            "step": final_state.get("step", 0),
            "phase": final_state.get("phase", "UNKNOWN"),
        }

    def replay_to_step(self, target_step: int) -> Dict[str, Any]:
        """
        Replay execution up to a specific step.

        Args:
            target_step: Target step number

        Returns:
            Summary of replayed execution
        """
        events_up_to = self.get_events_up_to_step(target_step)

        tool_calls = [e for e in events_up_to if e.get("t") == "tool_call"]
        tool_results = [e for e in events_up_to if e.get("t") == "tool_result"]
        llm_calls = [e for e in events_up_to if e.get("t") == "llm_call"]
        llm_results = [e for e in events_up_to if e.get("t") == "llm_result"]
        state_changes = [e for e in events_up_to if e.get("t") == "state_change"]

        return {
            "target_step": target_step,
            "total_events": len(events_up_to),
            "tool_calls": len(tool_calls),
            "tool_results": len(tool_results),
            "llm_calls": len(llm_calls),
            "llm_results": len(llm_results),
            "state_changes": len(state_changes),
            "final_state": state_changes[-1] if state_changes else None,
        }

    def get_reproduce_commands(self) -> List[str]:
        """
        Extract reproduce commands from events.

        Returns:
            List of commands that can be used to reproduce the execution
        """
        commands = []

        # Get all tool calls that are "run" commands
        tool_calls = self.get_tool_calls()
        for call in tool_calls:
            if call.get("tool") == "run":
                args = call.get("args", {})
                cmd = args.get("cmd", "")
                if cmd:
                    commands.append(cmd)

        return commands

    def get_final_diff(self) -> Optional[str]:
        """
        Get the final diff from events.

        Returns:
            Final diff string or None
        """
        # Look for get_diff tool results or diff in artifacts
        # First, try to get diff from artifacts (current_diff) in state_summary
        state_changes = self.get_state_changes()
        for state in reversed(state_changes):  # Start from the end
            # Check state_summary for artifacts
            state_summary = state.get("state", {})
            artifacts = state_summary.get("artifacts", {})
            current_diff = artifacts.get("current_diff", "")
            if current_diff:
                return current_diff

        # Fallback: look for get_diff tool results (if we add it as a tool in the future)
        tool_results = self.get_tool_results()
        for result in reversed(tool_results):  # Start from the end
            if result.get("tool") == "get_diff":
                stdout = result.get("stdout", "")
                if stdout:
                    return stdout

        return None

    def get_test_results(self) -> Optional[str]:
        """
        Get test results from events.

        Returns:
            Test results string or None
        """
        # Look for test command results
        # First, find tool_call events with test commands
        tool_calls = self.get_tool_calls()
        test_calls = []
        for call in tool_calls:
            if call.get("tool") == "run":
                args = call.get("args", {})
                cmd = args.get("cmd", "")
                if cmd and (
                    "test" in cmd.lower() or "pytest" in cmd.lower() or "npm test" in cmd.lower()
                ):
                    test_calls.append(call)

        # Then find corresponding tool_result events
        tool_results = self.get_tool_results()
        for call in reversed(test_calls):  # Start from the end
            call_step = call.get("step", 0)
            # Find result for the same step
            for result in reversed(tool_results):
                if result.get("step") == call_step and result.get("tool") == "run":
                    stdout = result.get("stdout", "")
                    if stdout:
                        return stdout

        return None
