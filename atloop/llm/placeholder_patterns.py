"""Placeholder pattern definitions and utilities.

This module centralizes all placeholder-related regex patterns and constants
to avoid duplication and ensure consistency across the codebase.
"""

import re
from typing import List, Tuple

# Placeholder type constants
PLACEHOLDER_TYPES = [
    "WRITE_FILE_CONTENT",
    "EDIT_FILE_CONTENT",
    "APPEND_FILE_CONTENT",
    "SHELL_COMMAND",
    "PYTHON_SCRIPT",
    "SHELL_SCRIPT",
]

# Pattern components
PLACEHOLDER_TYPE_PATTERN = "|".join(PLACEHOLDER_TYPES)
# Name pattern: any characters except "))---" sequence (which ends the delimiter)
PLACEHOLDER_NAME_PATTERN = r"(?:(?!\)\)---).)+"
# Line start pattern: must be at start of line (preceded by newline or start of text)
LINE_START_PATTERN = r"(?:^|\n)"

# Full placeholder delimiter pattern (for matching the delimiter itself)
# Format: ---((TYPE_name))---
# Captures: group 1 = type, group 2 = name
# Note: We need to wrap PLACEHOLDER_NAME_PATTERN in parentheses to capture it
PLACEHOLDER_DELIMITER_PATTERN = (
    rf"{LINE_START_PATTERN}---\(\(({PLACEHOLDER_TYPE_PATTERN})_({PLACEHOLDER_NAME_PATTERN})\)\)---"
)

# Compiled regex for delimiter matching (with capturing groups)
PLACEHOLDER_DELIMITER_REGEX = re.compile(PLACEHOLDER_DELIMITER_PATTERN)

# Pattern for removing placeholder sections (includes content until next placeholder or end)
# This is more complex as it needs to match the delimiter and all content until the next delimiter
# Note: We use non-capturing groups for the type pattern in lookahead
PLACEHOLDER_SECTION_PATTERN = (
    rf"{LINE_START_PATTERN}---\(\(({PLACEHOLDER_TYPE_PATTERN})_{PLACEHOLDER_NAME_PATTERN}\)\)---"
    r".*?"
    rf"(?={LINE_START_PATTERN}---\(\(({PLACEHOLDER_TYPE_PATTERN})_{PLACEHOLDER_NAME_PATTERN}\)\)---|$)"
)

# Compiled regex for section removal
PLACEHOLDER_SECTION_REGEX = re.compile(PLACEHOLDER_SECTION_PATTERN, re.DOTALL)

# Pattern for detecting partial placeholders (may be cut off in streaming)
# Note: Uses non-greedy *? instead of + to allow empty names (partial match)
PARTIAL_PLACEHOLDER_PATTERN = (
    rf"{LINE_START_PATTERN}---\(\({PLACEHOLDER_TYPE_PATTERN}_(?:(?!\)\)---).)*?\)?\)?---?"
)

# Compiled regex for partial placeholder detection
PARTIAL_PLACEHOLDER_REGEX = re.compile(PARTIAL_PLACEHOLDER_PATTERN)


def find_placeholder_delimiters(text: str) -> List[re.Match]:
    """
    Find all placeholder delimiters in text.

    Args:
        text: Text to search

    Returns:
        List of regex matches for placeholder delimiters
    """
    return list(PLACEHOLDER_DELIMITER_REGEX.finditer(text))


def extract_placeholder_name(match: re.Match) -> Tuple[str, str]:
    """
    Extract placeholder type and name from a delimiter match.

    Args:
        match: Regex match from PLACEHOLDER_DELIMITER_REGEX

    Returns:
        Tuple of (type, full_placeholder_name)
        Example: ("WRITE_FILE_CONTENT", "WRITE_FILE_CONTENT_file:test.py")
    """
    placeholder_type = match.group(1)
    placeholder_name = match.group(2)
    full_name = f"{placeholder_type}_{placeholder_name}"
    return placeholder_type, full_name
