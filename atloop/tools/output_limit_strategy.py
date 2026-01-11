"""Unified output limit strategy system.

This module provides a centralized system for determining output size limits
based on semantic types rather than tool names. This makes the system more
flexible, maintainable, and less prone to missing edge cases.
"""

from typing import Any, Dict, Optional

from atloop.config.limits import (
    MEMORY_SUMMARY_STDOUT_STDERR_OTHER,
    MEMORY_SUMMARY_STDOUT_STDERR_SHELL,
    STDOUT_STDERR_LIMIT_FILE_VIEW,
    STDOUT_STDERR_LIMIT_NORMAL,
    STDOUT_STDERR_LIMIT_OTHER,
    is_file_view_command,
)

from atloop.tools.base import BaseTool
from atloop.tools.output_semantic_type import OutputSemanticType


class OutputLimitStrategy:
    """Unified output limit strategy system.
    
    This class maps semantic types to appropriate output limits for different
    contexts (formatting vs memory summary). It provides a single source of
    truth for output size limits.
    """

    # Semantic type to limit mapping for formatting (last_error.summary)
    SEMANTIC_TYPE_LIMITS = {
        OutputSemanticType.KNOWLEDGE_CONTENT: STDOUT_STDERR_LIMIT_FILE_VIEW,  # 60KB
        OutputSemanticType.FILE_CONTENT: STDOUT_STDERR_LIMIT_FILE_VIEW,  # 60KB
        OutputSemanticType.FILE_VIEW_RESULT: STDOUT_STDERR_LIMIT_FILE_VIEW,  # 60KB
        OutputSemanticType.EXECUTION_RESULT: STDOUT_STDERR_LIMIT_NORMAL,  # 8KB
        OutputSemanticType.STATUS_MESSAGE: STDOUT_STDERR_LIMIT_OTHER,  # 2KB
        OutputSemanticType.ERROR_MESSAGE: STDOUT_STDERR_LIMIT_NORMAL,  # 8KB
    }

    # Semantic type to limit mapping for memory summary
    MEMORY_SUMMARY_LIMITS = {
        OutputSemanticType.KNOWLEDGE_CONTENT: MEMORY_SUMMARY_STDOUT_STDERR_SHELL,  # 12KB
        OutputSemanticType.FILE_CONTENT: MEMORY_SUMMARY_STDOUT_STDERR_SHELL,  # 12KB
        OutputSemanticType.FILE_VIEW_RESULT: MEMORY_SUMMARY_STDOUT_STDERR_SHELL,  # 12KB
        OutputSemanticType.EXECUTION_RESULT: MEMORY_SUMMARY_STDOUT_STDERR_SHELL,  # 12KB
        OutputSemanticType.STATUS_MESSAGE: MEMORY_SUMMARY_STDOUT_STDERR_OTHER,  # 4KB
        OutputSemanticType.ERROR_MESSAGE: MEMORY_SUMMARY_STDOUT_STDERR_SHELL,  # 12KB
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
        semantic_type = (
            tool.stderr_semantic_type if is_stderr else tool.stdout_semantic_type
        )

        # Special handling: run command file viewing
        if tool.name == "run" and args:
            cmd = args.get("cmd", "")
            if is_file_view_command(cmd):
                return STDOUT_STDERR_LIMIT_FILE_VIEW

        # Return corresponding limit
        return cls.SEMANTIC_TYPE_LIMITS.get(
            semantic_type, STDOUT_STDERR_LIMIT_OTHER  # Default fallback
        )

    @classmethod
    def get_limit_for_memory_summary(
        cls, tool: BaseTool, is_stderr: bool = False
    ) -> int:
        """Get output limit for memory summary.
        
        Args:
            tool: Tool instance
            is_stderr: Whether this is stderr (True) or stdout (False)
        
        Returns:
            Output limit in characters
        """
        semantic_type = (
            tool.stderr_semantic_type if is_stderr else tool.stdout_semantic_type
        )

        return cls.MEMORY_SUMMARY_LIMITS.get(
            semantic_type, MEMORY_SUMMARY_STDOUT_STDERR_OTHER  # Default fallback
        )
