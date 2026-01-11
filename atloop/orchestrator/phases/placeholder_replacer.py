"""Placeholder replacement service for type-specific placeholders.

This module provides a clean, testable service for replacing type-specific
placeholders (WRITE_FILE_CONTENT_#N, EDIT_FILE_CONTENT_#N, etc.) with actual
content in action dictionaries.

Design:
- Each tool type has its own placeholder prefix for type safety
- Strict validation ensures tools use correct placeholder types
- Backward compatibility: old FILE_CONTENT_#N still works (with deprecation warning)
"""

import logging
import re
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
        "WRITE_FILE_CONTENT": "WRITE_FILE_CONTENT_#",
        "EDIT_FILE_CONTENT": "EDIT_FILE_CONTENT_#",
        "APPEND_FILE_CONTENT": "APPEND_FILE_CONTENT_#",
        "SHELL_COMMAND": "SHELL_COMMAND_#",
        "PYTHON_SCRIPT": "PYTHON_SCRIPT_#",
        "SHELL_SCRIPT": "SHELL_SCRIPT_#",
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
    CONTENT_TOOLS = {"write_file", "append_file", "edit_file", "run", "run_python_script_string", "run_shell_script_string"}

    # Legacy placeholder (for backward compatibility)
    LEGACY_PLACEHOLDER_PREFIX = "FILE_CONTENT_#"

    @classmethod
    def _detect_placeholder_type(cls, placeholder: str) -> Optional[str]:
        """
        Detect the type of a placeholder.

        Args:
            placeholder: Placeholder string (e.g., "WRITE_FILE_CONTENT_#1")

        Returns:
            Placeholder type name (e.g., "WRITE_FILE_CONTENT") or None if invalid
        """
        for ptype, prefix in cls.PLACEHOLDER_TYPES.items():
            if placeholder.startswith(prefix):
                return ptype

        # Check for legacy placeholder
        if placeholder.startswith(cls.LEGACY_PLACEHOLDER_PREFIX):
            return "LEGACY"

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
                if suffix.isdigit():
                    return True

        # Check legacy placeholder
        if value.startswith(cls.LEGACY_PLACEHOLDER_PREFIX):
            suffix = value[len(cls.LEGACY_PLACEHOLDER_PREFIX) :]
            if suffix.isdigit():
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
        if placeholder_type == "LEGACY":
            # Legacy placeholder - allow but warn
            logger.warning(
                f"[PlaceholderReplacer] Tool {tool} uses legacy placeholder {placeholder}. "
                f"Please use type-specific placeholder: {', '.join(expected_types)}"
            )
            return True, None

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
            placeholder_field = None
            placeholder_value = None

            if tool in cls.CONTENT_TOOLS:
                # For file tools, check 'content' field
                if tool in {"write_file", "edit_file", "append_file"}:
                    placeholder_value = args.get("content", "")
                    placeholder_field = "content"
                # For run tool, check 'cmd' field
                elif tool == "run":
                    placeholder_value = args.get("cmd", "")
                    placeholder_field = "cmd"
                # For script tools, check 'script' field
                elif tool in {"run_python_script_string", "run_shell_script_string"}:
                    placeholder_value = args.get("script", "")
                    placeholder_field = "script"

            # Check if it's a placeholder
            if placeholder_field and cls._is_valid_placeholder(placeholder_value):
                # Validate placeholder type matches tool
                is_valid, error_msg = cls._validate_placeholder_type(tool, placeholder_value)
                if not is_valid:
                    type_mismatches.append(f"Action {i+1} ({tool}): {error_msg}")
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
                    missing_placeholders.append(placeholder_value)
                    logger.warning(
                        f"[PlaceholderReplacer] Missing placeholder {placeholder_value} for {tool} "
                        f"(action {i+1}) - will retry in next iteration"
                    )
                    pending_actions.append(action.copy())
            else:
                # Not a placeholder or tool doesn't use placeholders
                # Create a copy to maintain immutability
                successful_actions.append(action.copy())

        if missing_placeholders:
            logger.warning(
                f"[PlaceholderReplacer] Found {len(missing_placeholders)} missing placeholders: "
                f"{missing_placeholders}"
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
            if tool in {"write_file", "edit_file", "append_file"}:
                value = args.get("content", "")
            elif tool == "run":
                value = args.get("cmd", "")
            elif tool in {"run_python_script_string", "run_shell_script_string"}:
                value = args.get("script", "")
            else:
                continue

            if cls._is_valid_placeholder(value):
                remaining_placeholders.append(f"Action {i+1} ({tool}): {value}")

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
                logger.warning(
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
                logger.warning(
                    f"[PlaceholderReplacer] {error_msg}. "
                    f"Successful actions: {result.replaced_count}/{result.total_count}. "
                    f"Pending actions will be retried in next iteration."
                )

        return result.successful_actions, result
