"""Placeholder replacement service for type-specific placeholders.

This module provides a clean, testable service for replacing type-specific
placeholders (WRITE_FILE_CONTENT_descriptive-name, EDIT_FILE_CONTENT_descriptive-name, etc.)
with actual content in action dictionaries.

Design:
- Each tool type has its own placeholder prefix for type safety
- Strict validation ensures tools use correct placeholder types
- Placeholders use descriptive names (not numbers) for better readability
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class PlaceholderReplacementError(Exception):
    """Raised when placeholder replacement fails."""

    def __init__(self, message: str, missing_placeholders: List[str]):
        super().__init__(message)
        self.missing_placeholders = missing_placeholders


@dataclass
class PlaceholderReplacementResult:
    """Result of placeholder replacement with partial success support."""

    successful_actions: List[Dict]  # Actions with all placeholders replaced
    pending_actions: List[Dict]  # Actions with missing placeholders
    missing_placeholders: List[str]  # List of missing placeholder IDs
    type_mismatches: List[str]  # List of type mismatch errors
    replaced_count: int
    total_count: int


class PlaceholderReplacer:
    """Service for replacing type-specific placeholders in actions."""

    # Placeholder type definitions
    PLACEHOLDER_TYPES = {
        "WRITE_FILE_CONTENT": "WRITE_FILE_CONTENT_",
        "EDIT_FILE_CONTENT": "EDIT_FILE_CONTENT_",
        "APPEND_FILE_CONTENT": "APPEND_FILE_CONTENT_",
        "SHELL_COMMAND": "SHELL_COMMAND_",
        "PYTHON_SCRIPT": "PYTHON_SCRIPT_",
        "SHELL_SCRIPT": "SHELL_SCRIPT_",
    }

    # Mapping of tools to their expected placeholder types
    TOOL_PLACEHOLDER_MAP: Dict[str, Set[str]] = {
        "write_file": {"WRITE_FILE_CONTENT"},
        "edit_file": {"EDIT_FILE_CONTENT"},
        "append_file": {"APPEND_FILE_CONTENT"},
        "run": {"SHELL_COMMAND"},
        "run_python_script_string": {"PYTHON_SCRIPT"},
        "run_shell_script_string": {"SHELL_SCRIPT"},
    }

    # Tools that use content placeholders
    CONTENT_TOOLS = {
        "write_file",
        "append_file",
        "edit_file",
        "run",
        "run_python_script_string",
        "run_shell_script_string",
    }

    @classmethod
    def get_placeholder_field_value(
        cls, tool: str, args: Dict
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Get the placeholder field name and value for a tool.

        Args:
            tool: Tool name
            args: Tool arguments

        Returns:
            Tuple of (field_name, field_value) or (None, None) if tool doesn't use placeholders
        """
        if tool not in cls.CONTENT_TOOLS:
            return None, None

        if tool in {"write_file", "edit_file", "append_file"}:
            return "content", args.get("content", "")
        elif tool == "run":
            return "cmd", args.get("cmd", "")
        elif tool in {"run_python_script_string", "run_shell_script_string"}:
            return "script", args.get("script", "")
        else:
            return None, None

    @classmethod
    def _detect_placeholder_type(cls, placeholder: str) -> Optional[str]:
        """
        Detect the type of a placeholder.

        Args:
            placeholder: Placeholder string (e.g., "WRITE_FILE_CONTENT_descriptive-name")

        Returns:
            Placeholder type name (e.g., "WRITE_FILE_CONTENT") or None if invalid
        """
        for ptype, prefix in cls.PLACEHOLDER_TYPES.items():
            if placeholder.startswith(prefix):
                # Check that there's a name after the prefix (can be any string)
                suffix = placeholder[len(prefix) :]
                if suffix:  # Any non-empty string is valid
                    return ptype

        return None

    @classmethod
    def _is_valid_placeholder(cls, value: str) -> bool:
        """
        Check if a value is a valid placeholder.

        Args:
            value: Value to check

        Returns:
            True if valid placeholder format
        """
        if not isinstance(value, str):
            return False

        # Check type-specific placeholders
        for prefix in cls.PLACEHOLDER_TYPES.values():
            if value.startswith(prefix):
                suffix = value[len(prefix) :]
                # Name must be non-empty (can contain any characters)
                if suffix:
                    return True

        return False

    @classmethod
    def _validate_placeholder_type(cls, tool: str, placeholder: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that a placeholder type matches the tool.

        Args:
            tool: Tool name
            placeholder: Placeholder string

        Returns:
            Tuple of (is_valid, error_message)
        """
        expected_types = cls.TOOL_PLACEHOLDER_MAP.get(tool)
        if not expected_types:
            # Tool doesn't use placeholders
            return True, None

        placeholder_type = cls._detect_placeholder_type(placeholder)
        if placeholder_type is None:
            return False, f"Invalid placeholder format: {placeholder}"

        # Map placeholder type to expected set
        if placeholder_type not in expected_types:
            expected_str = ", ".join(expected_types)
            return False, (
                f"Placeholder type mismatch: tool '{tool}' expects {expected_str}, "
                f"but got {placeholder_type} placeholder '{placeholder}'"
            )

        return True, None

    @classmethod
    def _replace_placeholders_internal(
        cls, actions: List[Dict], file_contents: Dict[str, str]
    ) -> PlaceholderReplacementResult:
        """
        Internal method that returns PlaceholderReplacementResult.

        This is the core implementation used by both replace_placeholders and replace_and_validate.
        """
        successful_actions = []
        pending_actions = []
        missing_placeholders = []
        type_mismatches = []

        logger.debug(
            f"[PlaceholderReplacer] Processing {len(actions)} actions, "
            f"file_contents keys: {list(file_contents.keys())}"
        )

        for i, action in enumerate(actions):
            tool = action.get("tool")
            args = action.get("args", {})

            # Determine which field contains the placeholder
            placeholder_field, placeholder_value = cls.get_placeholder_field_value(tool, args)

            # Check if it's a placeholder
            if placeholder_field and cls._is_valid_placeholder(placeholder_value):
                # Validate placeholder type matches tool
                is_valid, error_msg = cls._validate_placeholder_type(tool, placeholder_value)
                if not is_valid:
                    type_mismatches.append(f"Action {i + 1} ({tool}): {error_msg}")
                    # Still add to pending - LLM needs to fix the type
                    pending_actions.append(action.copy())
                    continue

                # Check if placeholder is available
                if placeholder_value in file_contents:
                    # Replace placeholder with actual content
                    new_args = args.copy()
                    new_args[placeholder_field] = file_contents[placeholder_value]
                    new_action = action.copy()
                    new_action["args"] = new_args

                    successful_actions.append(new_action)
                    logger.info(
                        f"[PlaceholderReplacer] Replaced {placeholder_value} for {tool} "
                        f"({len(file_contents[placeholder_value])} chars)"
                    )
                else:
                    # Placeholder not found - mark as pending
                    # This is a normal business case - LLM may provide it in next iteration
                    missing_placeholders.append(placeholder_value)
                    logger.debug(
                        f"[PlaceholderReplacer] Missing placeholder {placeholder_value} for {tool} "
                        f"(action {i + 1}) - will retry in next iteration"
                    )
                    pending_actions.append(action.copy())
            else:
                # Not a placeholder or tool doesn't use placeholders
                # Create a copy to maintain immutability
                successful_actions.append(action.copy())

        if missing_placeholders:
            # This is a normal business case - LLM may provide placeholders in next iteration
            # Agent loop can handle this gracefully
            logger.debug(
                f"[PlaceholderReplacer] Found {len(missing_placeholders)} missing placeholders: "
                f"{missing_placeholders} (will retry in next iteration)"
            )

        if type_mismatches:
            logger.error(
                f"[PlaceholderReplacer] Found {len(type_mismatches)} type mismatches: "
                f"{type_mismatches}"
            )

        return PlaceholderReplacementResult(
            successful_actions=successful_actions,
            pending_actions=pending_actions,
            missing_placeholders=missing_placeholders,
            type_mismatches=type_mismatches,
            replaced_count=len(successful_actions),
            total_count=len(actions),
        )

    @classmethod
    def replace_placeholders(
        cls, actions: List[Dict], file_contents: Dict[str, str]
    ) -> Tuple[List[Dict], List[str]]:
        """
        Replace type-specific placeholders with actual content.

        This method creates new action dictionaries (immutable replacement)
        to ensure the original actions are not modified.

        Args:
            actions: List of action dictionaries from LLM
            file_contents: Dictionary mapping placeholder names to actual content

        Returns:
            Tuple of (replaced_actions, missing_placeholders)
            - replaced_actions: All actions (successful + pending with placeholders)
            - missing_placeholders: List of placeholders that were not found
        """
        result = cls._replace_placeholders_internal(actions, file_contents)
        # Return tuple for backward compatibility
        # All actions include both successful and pending (pending still have placeholders)
        all_actions = result.successful_actions + result.pending_actions
        return all_actions, result.missing_placeholders

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
            args = action.get("args", {})

            # Check appropriate field based on tool
            field_name, value = cls.get_placeholder_field_value(tool, args)
            if field_name is None:
                continue

            if cls._is_valid_placeholder(value):
                remaining_placeholders.append(f"Action {i + 1} ({tool}): {value}")

        is_valid = len(remaining_placeholders) == 0
        return is_valid, remaining_placeholders

    @classmethod
    def replace_and_validate(
        cls, actions: List[Dict], file_contents: Dict[str, str], strict: bool = True
    ) -> List[Dict]:
        """
        Replace placeholders and validate the result.

        This is the main entry point that combines replacement and validation.
        Supports partial success: returns all actions (successful + pending).

        Args:
            actions: List of action dictionaries from LLM
            file_contents: Dictionary mapping placeholder names to actual content
            strict: If True, raise exception on missing placeholders. If False, allow partial success.

        Returns:
            List of actions (successful actions with placeholders replaced + pending actions with placeholders)

        Raises:
            PlaceholderReplacementError: If strict=True and placeholders are missing
        """
        result = cls._replace_placeholders_internal(actions, file_contents)

        # Check for type mismatches (always an error)
        if result.type_mismatches:
            error_msg = (
                f"Placeholder type validation failed. "
                f"Found {len(result.type_mismatches)} type mismatches: {result.type_mismatches}"
            )
            if strict:
                raise PlaceholderReplacementError(error_msg, result.missing_placeholders)
            else:
                logger.error(f"[PlaceholderReplacer] {error_msg}")

        # Check for missing placeholders
        if result.missing_placeholders:
            error_msg = (
                f"Placeholder replacement incomplete. "
                f"Found {len(result.missing_placeholders)} missing placeholders: {result.missing_placeholders}"
            )
            if strict:
                raise PlaceholderReplacementError(error_msg, result.missing_placeholders)
            else:
                # This is a normal business case - LLM may provide placeholders in next iteration
                # Agent loop can handle this gracefully, so use debug level
                logger.debug(
                    f"[PlaceholderReplacer] {error_msg}. "
                    f"Successful actions: {result.replaced_count}/{result.total_count}. "
                    f"Pending actions will be retried in next iteration."
                )

        # Return all actions (successful + pending) for backward compatibility
        return result.successful_actions + result.pending_actions

    @classmethod
    def replace_and_validate_with_result(
        cls, actions: List[Dict], file_contents: Dict[str, str], strict: bool = True
    ) -> Tuple[List[Dict], PlaceholderReplacementResult]:
        """
        Replace placeholders and validate the result, returning full result metadata.

        This method is used by PlanPhase to get detailed information about partial success.

        Args:
            actions: List of action dictionaries from LLM
            file_contents: Dictionary mapping placeholder names to actual content
            strict: If True, raise exception on missing placeholders. If False, allow partial success.

        Returns:
            Tuple of (successful_actions, replacement_result)
            - successful_actions: Actions with all placeholders replaced (ready to execute)
            - replacement_result: Full result with pending actions and metadata

        Raises:
            PlaceholderReplacementError: If strict=True and placeholders are missing
        """
        result = cls._replace_placeholders_internal(actions, file_contents)

        # Check for type mismatches (always an error)
        if result.type_mismatches:
            error_msg = (
                f"Placeholder type validation failed. "
                f"Found {len(result.type_mismatches)} type mismatches: {result.type_mismatches}"
            )
            if strict:
                raise PlaceholderReplacementError(error_msg, result.missing_placeholders)
            else:
                logger.error(f"[PlaceholderReplacer] {error_msg}")

        # Check for missing placeholders
        if result.missing_placeholders:
            error_msg = (
                f"Placeholder replacement incomplete. "
                f"Found {len(result.missing_placeholders)} missing placeholders: {result.missing_placeholders}"
            )
            if strict:
                raise PlaceholderReplacementError(error_msg, result.missing_placeholders)
            else:
                # This is a normal business case - LLM may provide placeholders in next iteration
                # Agent loop can handle this gracefully, so use debug level
                logger.debug(
                    f"[PlaceholderReplacer] {error_msg}. "
                    f"Successful actions: {result.replaced_count}/{result.total_count}. "
                    f"Pending actions will be retried in next iteration."
                )

        return result.successful_actions, result
