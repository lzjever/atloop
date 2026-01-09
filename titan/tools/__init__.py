"""Tools module for Titan agent."""

from titan.tools.base import BaseTool, ToolResult

# Import ToolRegistry lazily to avoid circular imports
__all__ = [
    "ToolResult",
    "BaseTool",
]
