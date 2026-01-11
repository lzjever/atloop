"""Placeholder replacement service for file content placeholders.

This module provides a clean, testable service for replacing FILE_CONTENT_#N
placeholders with actual file contents in action dictionaries.
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PlaceholderReplacementError(Exception):
    """Raised when placeholder replacement fails."""

    def __init__(self, message: str, missing_placeholders: List[str]):
        super().__init__(message)
        self.missing_placeholders = missing_placeholders


class PlaceholderReplacer:
    """Service for replacing FILE_CONTENT_#N placeholders in actions."""

    # Tools that use content placeholders
    CONTENT_TOOLS = {"write_file", "append_file", "edit_file"}

    @classmethod
    def replace_placeholders(
        cls, actions: List[Dict], file_contents: Dict[str, str]
    ) -> Tuple[List[Dict], List[str]]:
        """
        Replace FILE_CONTENT_#N placeholders with actual content.

        This method creates new action dictionaries (immutable replacement)
        to ensure the original actions are not modified.

        Args:
            actions: List of action dictionaries from LLM
            file_contents: Dictionary mapping placeholder names to actual content

        Returns:
            Tuple of (replaced_actions, missing_placeholders)
            - replaced_actions: New list of actions with placeholders replaced
            - missing_placeholders: List of placeholders that were not found
                                  (for validation/warning purposes)

        Raises:
            PlaceholderReplacementError: If critical placeholders are missing
        """
        replaced_actions = []
        missing_placeholders = []

        logger.debug(
            f"[PlaceholderReplacer] Processing {len(actions)} actions, "
            f"file_contents keys: {list(file_contents.keys())}"
        )

        for i, action in enumerate(actions):
            tool = action.get("tool")
            args = action.get("args", {})

            # Only process tools that use content placeholders
            if tool not in cls.CONTENT_TOOLS:
                # For non-content tools, create a shallow copy to maintain immutability
                replaced_actions.append(action.copy())
                continue

            content = args.get("content", "")
            # Valid placeholder format: FILE_CONTENT_#N where N is one or more digits
            is_placeholder = (
                isinstance(content, str)
                and content.startswith("FILE_CONTENT_#")
                and len(content) > len("FILE_CONTENT_#")
                and content[len("FILE_CONTENT_#") :].isdigit()
            )

            if is_placeholder:
                if content in file_contents:
                    # Replace placeholder with actual content
                    new_args = args.copy()
                    new_args["content"] = file_contents[content]
                    new_action = action.copy()
                    new_action["args"] = new_args

                    replaced_actions.append(new_action)
                    logger.info(
                        f"[PlaceholderReplacer] Replaced {content} for {tool} "
                        f"({len(file_contents[content])} chars)"
                    )
                else:
                    # Placeholder not found - this is an error
                    missing_placeholders.append(content)
                    logger.error(
                        f"[PlaceholderReplacer] Missing placeholder {content} for {tool} "
                        f"(action {i+1})"
                    )
                    # Still append the action (with placeholder) so we can detect the error
                    # The validation layer will catch this
                    replaced_actions.append(action.copy())
            else:
                # Not a placeholder - content is already actual content
                # Create a copy to maintain immutability
                replaced_actions.append(action.copy())

        if missing_placeholders:
            logger.warning(
                f"[PlaceholderReplacer] Found {len(missing_placeholders)} missing placeholders: "
                f"{missing_placeholders}"
            )

        return replaced_actions, missing_placeholders

    @classmethod
    def validate_replacement(
        cls, actions: List[Dict], file_contents: Dict[str, str]
    ) -> Tuple[bool, List[str]]:
        """
        Validate that all placeholders have been replaced.

        Args:
            actions: List of action dictionaries (should be after replacement)
            file_contents: Dictionary of available file contents

        Returns:
            Tuple of (is_valid, remaining_placeholders)
        """
        remaining_placeholders = []

        for i, action in enumerate(actions):
            tool = action.get("tool")
            if tool not in cls.CONTENT_TOOLS:
                continue

            content = action.get("args", {}).get("content", "")
            # Valid placeholder format: FILE_CONTENT_#N where N is one or more digits
            is_valid_placeholder = (
                isinstance(content, str)
                and content.startswith("FILE_CONTENT_#")
                and len(content) > len("FILE_CONTENT_#")
                and content[len("FILE_CONTENT_#") :].isdigit()
            )
            if is_valid_placeholder:
                remaining_placeholders.append(f"Action {i+1} ({tool}): {content}")

        is_valid = len(remaining_placeholders) == 0
        return is_valid, remaining_placeholders

    @classmethod
    def replace_and_validate(
        cls, actions: List[Dict], file_contents: Dict[str, str], strict: bool = True
    ) -> List[Dict]:
        """
        Replace placeholders and validate the result.

        This is the main entry point that combines replacement and validation.

        Args:
            actions: List of action dictionaries from LLM
            file_contents: Dictionary mapping placeholder names to actual content
            strict: If True, raise exception on missing placeholders. If False, log warning.

        Returns:
            List of actions with placeholders replaced

        Raises:
            PlaceholderReplacementError: If strict=True and placeholders are missing
        """
        replaced_actions, missing_placeholders = cls.replace_placeholders(
            actions, file_contents
        )

        # Validate replacement
        is_valid, remaining = cls.validate_replacement(replaced_actions, file_contents)

        if not is_valid:
            error_msg = (
                f"Placeholder replacement validation failed. "
                f"Found {len(remaining)} unreplaced placeholders: {remaining}"
            )
            if strict:
                raise PlaceholderReplacementError(error_msg, missing_placeholders)
            else:
                logger.warning(f"[PlaceholderReplacer] {error_msg}")

        return replaced_actions
