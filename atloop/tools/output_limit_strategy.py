"""Unified output limit strategy system.

This module provides a centralized system for determining output size limits
based on semantic types rather than tool names. This makes the system more
flexible, maintainable, and less prone to missing edge cases.
"""

from typing import Any, Dict, Optional

from atloop.config.loader import ConfigLoader
from atloop.tools.base import BaseTool
from atloop.tools.output_semantic_type import OutputSemanticType


def _is_file_view_command(cmd: str) -> bool:
    """Check if command is a file view command."""
    cmd_lower = cmd.lower()
    return any(cmd in cmd_lower for cmd in ["cat ", "head ", "tail ", "sed -n"])


class OutputLimitStrategy:
    """Unified output limit strategy system.

    This class maps semantic types to appropriate output limits for different
    contexts (formatting vs memory summary). It provides a single source of
    truth for output size limits.

    Limits are loaded from configuration at runtime to allow customization.
    """

    @classmethod
    def _get_limits(cls):
        """Get limits from configuration."""
        config = ConfigLoader.get()
        return {
            "output": {
                "file_view": config.limits.output.file_view,
                "normal": config.limits.output.normal,
                "other": config.limits.output.other,
            },
            "memory": {
                "shell": config.memory.summary_stdout_stderr_shell,
                "other": config.memory.summary_stdout_stderr_other,
            },
        }

    @classmethod
    def _get_semantic_type_limits(cls):
        """Get semantic type to limit mapping for formatting (last_error.summary)."""
        limits = cls._get_limits()
        return {
            OutputSemanticType.KNOWLEDGE_CONTENT: limits["output"]["file_view"],
            OutputSemanticType.FILE_CONTENT: limits["output"]["file_view"],
            OutputSemanticType.FILE_VIEW_RESULT: limits["output"]["file_view"],
            OutputSemanticType.EXECUTION_RESULT: limits["output"]["normal"],
            OutputSemanticType.STATUS_MESSAGE: limits["output"]["other"],
            OutputSemanticType.ERROR_MESSAGE: limits["output"]["normal"],
        }

    @classmethod
    def _get_memory_summary_limits(cls):
        """Get semantic type to limit mapping for memory summary."""
        limits = cls._get_limits()
        return {
            OutputSemanticType.KNOWLEDGE_CONTENT: limits["memory"]["shell"],
            OutputSemanticType.FILE_CONTENT: limits["memory"]["shell"],
            OutputSemanticType.FILE_VIEW_RESULT: limits["memory"]["shell"],
            OutputSemanticType.EXECUTION_RESULT: limits["memory"]["shell"],
            OutputSemanticType.STATUS_MESSAGE: limits["memory"]["other"],
            OutputSemanticType.ERROR_MESSAGE: limits["memory"]["shell"],
        }

    @classmethod
    def get_limit_for_formatting(
        cls,
        tool: BaseTool,
        is_stderr: bool = False,
        args: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Get output limit for formatting (last_error.summary).

        Args:
            tool: Tool instance
            is_stderr: Whether this is stderr (True) or stdout (False)
            args: Tool arguments (for special cases like run command file viewing)

        Returns:
            Output limit in characters
        """
        # Get semantic type
        semantic_type = tool.stderr_semantic_type if is_stderr else tool.stdout_semantic_type

        # Special handling: run command file viewing
        limits = cls._get_limits()
        if tool.name == "run" and args:
            cmd = args.get("cmd", "")
            if _is_file_view_command(cmd):
                return limits["output"]["file_view"]

        # Return corresponding limit
        semantic_limits = cls._get_semantic_type_limits()
        return semantic_limits.get(
            semantic_type,
            limits["output"]["other"],  # Default fallback
        )

    @classmethod
    def get_limit_for_memory_summary(cls, tool: BaseTool, is_stderr: bool = False) -> int:
        """Get output limit for memory summary.

        Args:
            tool: Tool instance
            is_stderr: Whether this is stderr (True) or stdout (False)

        Returns:
            Output limit in characters
        """
        semantic_type = tool.stderr_semantic_type if is_stderr else tool.stdout_semantic_type

        limits = cls._get_limits()
        memory_limits = cls._get_memory_summary_limits()
        return memory_limits.get(
            semantic_type,
            limits["memory"]["other"],  # Default fallback
        )
