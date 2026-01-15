"""Path validator for preventing path traversal attacks.

This module provides validation and sanitization for file paths to prevent
path traversal attacks and ensure files stay within allowed directories.
"""

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Exception raised for security violations."""

    pass


class PathValidator:
    """
    Validates file paths to prevent path traversal attacks.

    Ensures that:
    - Paths don't escape the allowed base directory
    - Paths are normalized and canonical
    - Symbolic links are resolved
    """

    def __init__(self, allowed_base: str = "/workspace"):
        """
        Initialize path validator.

        Args:
            allowed_base: Base directory that files must be within. Defaults to /workspace.
        """
        self.allowed_base = Path(allowed_base).resolve()

    def validate(self, path: str) -> Tuple[bool, Optional[str], Optional[Path]]:
        """
        Validate a file path.

        Args:
            path: File path to validate (can be relative or absolute)

        Returns:
            Tuple of (is_valid, error_message, resolved_path)
            - resolved_path is the normalized, absolute path if validation succeeds

        Raises:
            SecurityError: If path violates security policies
        """
        # Resolve to absolute path (follows symlinks)
        try:
            resolved_path = Path(path).resolve()
        except (OSError, RuntimeError) as e:
            logger.warning("Failed to resolve path: %s (%s)", path, e)
            return False, f"Invalid path: {path}", None

        # Check if path is within allowed base
        try:
            resolved_path.relative_to(self.allowed_base)
        except ValueError:
            logger.warning(
                "Path outside allowed base: %s (base: %s)",
                resolved_path,
                self.allowed_base,
            )
            return False, f"Path outside allowed directory ({self.allowed_base}): {path}", None

        logger.debug("Path validated successfully: %s", resolved_path)
        return True, None, resolved_path

    def validate_directory(self, path: str) -> Tuple[bool, Optional[str], Optional[Path]]:
        """
        Validate a directory path.

        Args:
            path: Directory path to validate

        Returns:
            Tuple of (is_valid, error_message, resolved_path)
        """
        # First validate as a regular path
        is_valid, error_msg, resolved_path = self.validate(path)

        if not is_valid:
            return is_valid, error_msg, None

        # Additional check: ensure it's a directory (if it exists)
        if resolved_path.exists() and not resolved_path.is_dir():
            return False, f"Path is not a directory: {path}", None

        return True, None, resolved_path

    def sanitize_path(self, path: str) -> str:
        """
        Sanitize a path string by removing dangerous components.

        Args:
            path: Path to sanitize

        Returns:
            Sanitized path string
        """
        # Remove any parent directory references
        sanitized = path.replace("..", "")

        # Remove extra slashes
        sanitized = os.path.normpath(sanitized)

        return sanitized


# Global validator instance with default settings
_default_validator: Optional[PathValidator] = None


def get_default_validator() -> PathValidator:
    """Get or create the default path validator instance."""
    global _default_validator
    if _default_validator is None:
        _default_validator = PathValidator()
    return _default_validator


def validate_path(
    path: str,
    allowed_base: str = "/workspace",
) -> Tuple[bool, Optional[str], Optional[Path]]:
    """
    Validate a file path for security.

    Convenience function that uses the default validator or creates a new one.

    Args:
        path: File path to validate
        allowed_base: Base directory that files must be within

    Returns:
        Tuple of (is_valid, error_message, resolved_path)
    """
    validator = PathValidator(allowed_base=allowed_base)
    return validator.validate(path)
