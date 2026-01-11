"""Unified error handling and recovery strategy."""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categories for classification."""

    RECOVERABLE = "recoverable"  # Can be recovered, workflow should continue
    FATAL = "fatal"  # Cannot be recovered, workflow should fail


class ErrorClassifier:
    """Classify errors into recoverable vs fatal categories."""

    # Recoverable error patterns (case-insensitive)
    RECOVERABLE_PATTERNS = [
        "timed out",
        "timeout",
        "connection",
        "network",
        "temporary",
        "retry",
        "rate limit",
        "quota",
        "service unavailable",
        "503",
        "502",
        "429",  # Too many requests
        "file not found",  # Can be handled by LLM
        "permission denied",  # Can be handled by LLM
        "command not found",  # Can be handled by LLM
    ]

    # Fatal error patterns (case-insensitive)
    FATAL_PATTERNS = [
        "invalid configuration",
        "missing required",
        "not initialized",
        "state transition failed",
        "unknown phase",
    ]

    @classmethod
    def classify(cls, error: Exception, error_msg: Optional[str] = None) -> ErrorCategory:
        """
        Classify an error as recoverable or fatal.

        Args:
            error: The exception object
            error_msg: Optional error message string (if different from str(error))

        Returns:
            ErrorCategory indicating if error is recoverable or fatal
        """
        error_str = error_msg or str(error)
        error_str_lower = error_str.lower()
        error_type_name = type(error).__name__.lower()

        # Check fatal patterns first
        for pattern in cls.FATAL_PATTERNS:
            if pattern in error_str_lower:
                logger.debug(f"[ErrorClassifier] Classified as FATAL (pattern: {pattern})")
                return ErrorCategory.FATAL

        # Check recoverable patterns
        for pattern in cls.RECOVERABLE_PATTERNS:
            if pattern in error_str_lower:
                logger.debug(f"[ErrorClassifier] Classified as RECOVERABLE (pattern: {pattern})")
                return ErrorCategory.RECOVERABLE

        # Check error type
        recoverable_types = [
            "timeouterror",
            "connectionerror",
            "httperror",
            "requestexception",
            "filenotfounderror",
            "permissionerror",
        ]
        if any(etype in error_type_name for etype in recoverable_types):
            logger.debug(f"[ErrorClassifier] Classified as RECOVERABLE (type: {error_type_name})")
            return ErrorCategory.RECOVERABLE

        # Default: treat as recoverable to give LLM a chance
        # Only truly fatal errors (config, state machine) should be fatal
        logger.debug(
            f"[ErrorClassifier] Default classification: RECOVERABLE (error: {error_str[:100]})"
        )
        return ErrorCategory.RECOVERABLE

    @classmethod
    def is_timeout(cls, error: Exception, error_msg: Optional[str] = None) -> bool:
        """Check if error is a timeout error."""
        error_str = error_msg or str(error)
        error_str_lower = error_str.lower()
        return "timed out" in error_str_lower or "timeout" in error_str_lower


class ErrorRecoveryStrategy:
    """Strategy for recovering from errors."""

    @staticmethod
    def get_recovery_phase(current_phase, error_category: ErrorCategory) -> str:
        """
        Determine which phase to transition to for error recovery.

        Args:
            current_phase: Current phase name
            error_category: Category of the error

        Returns:
            Phase name to transition to for recovery
        """
        if error_category == ErrorCategory.FATAL:
            return "FAIL"

        # For recoverable errors, transition back to PLAN to let LLM adjust
        # This gives LLM context about what went wrong and chance to fix it
        return "PLAN"

    @staticmethod
    def format_error_for_llm(
        error: Exception, error_category: ErrorCategory, context: Optional[str] = None
    ) -> str:
        """
        Format error message for LLM consumption.

        Args:
            error: The exception
            error_category: Category of the error
            context: Optional context about where error occurred

        Returns:
            Formatted error message for LLM
        """
        error_msg = str(error)
        error_type = type(error).__name__

        parts = []
        if context:
            parts.append(f"Context: {context}")

        if ErrorClassifier.is_timeout(error):
            parts.append(
                "⏱️ TIMEOUT: Command execution timed out.\n"
                "Suggestions:\n"
                "1. Increase timeout_sec parameter (e.g., timeout_sec=1200 for long-running commands)\n"
                "2. Break the command into smaller steps\n"
                "3. Check if the command is stuck or needs different approach"
            )
        elif error_category == ErrorCategory.RECOVERABLE:
            parts.append(f"⚠️ Recoverable error ({error_type}): {error_msg}")
            parts.append(
                "This error can potentially be recovered. Please adjust your approach and try again."
            )
        else:
            parts.append(f"❌ Fatal error ({error_type}): {error_msg}")

        return "\n\n".join(parts)
