"""Placeholder information tracking for memory recording.

This module provides a clean way to track placeholder information across phases
without polluting action dictionaries with temporary fields.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from atloop.orchestrator.phases.placeholder_replacer import PlaceholderReplacer

logger = logging.getLogger(__name__)


@dataclass
class PlaceholderInfo:
    """Information about a placeholder used in an action."""

    tool: str
    placeholder: Optional[str]  # Placeholder name if used, None otherwise
    args: Optional[Dict]  # Actual args if no placeholder, None if placeholder was used


class PlaceholderInfoTracker:
    """Tracks placeholder information for actions across phases."""

    @staticmethod
    def extract_placeholder_info(actions: List[Dict]) -> List[PlaceholderInfo]:
        """
        Extract placeholder information from actions before replacement.

        Args:
            actions: List of action dictionaries (before placeholder replacement)

        Returns:
            List of PlaceholderInfo objects, one per action
        """
        placeholder_info_list = []

        for action in actions:
            tool = action.get("tool", "")
            args = action.get("args", {})
            placeholder_name = None

            # Get placeholder field value using shared method
            field_name, value = PlaceholderReplacer.get_placeholder_field_value(tool, args)
            if field_name and PlaceholderReplacer._is_valid_placeholder(value):
                placeholder_name = value

            placeholder_info_list.append(
                PlaceholderInfo(
                    tool=tool,
                    placeholder=placeholder_name,
                    args=args.copy() if not placeholder_name else None,
                )
            )

        return placeholder_info_list

    @staticmethod
    def validate_run_tool_placeholders(
        actions: List[Dict],
    ) -> tuple[bool, Optional[str], Optional[int]]:
        """
        Validate that all run tool actions use placeholders.

        Args:
            actions: List of action dictionaries

        Returns:
            Tuple of (is_valid, error_message, action_index)
            If is_valid is False, error_message and action_index indicate the problem
        """
        for i, action in enumerate(actions):
            tool = action.get("tool", "")
            if tool == "run":
                cmd = action.get("args", {}).get("cmd", "")
                if cmd and not PlaceholderReplacer._is_valid_placeholder(cmd):
                    error_msg = (
                        f"run tool action {i + 1} must use SHELL_COMMAND_<description> placeholder, "
                        f"not direct command string. Got: {cmd[:50]}..."
                    )
                    return False, error_msg, i + 1

        return True, None, None
