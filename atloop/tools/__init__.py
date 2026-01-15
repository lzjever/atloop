"""Tools module for atloop agent."""

from atloop.tools.base import BaseTool, ToolResult

# Import ToolRuntime lazily to avoid circular imports
# ToolRuntime imports ToolRegistry, which may have dependencies
__all__ = [
    "ToolResult",
    "BaseTool",
    "ToolRuntime",  # Legacy compatibility - use ToolRegistry instead
]


def __getattr__(name: str):
    """Lazy import for ToolRuntime to avoid circular imports."""
    if name == "ToolRuntime":
        from atloop.tools.runtime import ToolRuntime

        return ToolRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
