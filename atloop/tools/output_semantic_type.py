"""Output semantic types for tools.

This module defines semantic types for tool outputs, which are used to determine
appropriate output size limits. Instead of hardcoding limits based on tool names,
we use semantic types to automatically apply the correct limits.
"""

from enum import Enum


class OutputSemanticType(Enum):
    """Semantic types for tool outputs.
    
    These types represent the nature of the output content, not the tool that
    produces it. This allows us to apply appropriate size limits based on
    what the output contains, rather than which tool produced it.
    """

    # Knowledge content - needs full display or large limit
    # Examples: skill content, documentation, reference materials
    KNOWLEDGE_CONTENT = "knowledge_content"

    # File content - needs full display or large limit
    # Examples: read_file, read_skill_file outputs
    FILE_CONTENT = "file_content"

    # Execution result - needs moderate limit
    # Examples: run command outputs (non-file-view)
    EXECUTION_RESULT = "execution_result"

    # File view result - needs large limit
    # Examples: run("cat file.txt") outputs
    FILE_VIEW_RESULT = "file_view_result"

    # Status message - can use small limit
    # Examples: write_file, edit_file success/failure messages
    STATUS_MESSAGE = "status_message"

    # Error message - needs moderate limit
    # Examples: stderr outputs
    ERROR_MESSAGE = "error_message"
