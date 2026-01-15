"""Tool runtime module."""

from atloop.runtime.sandbox_adapter import SandboxAdapter


# ToolRuntime has been moved to atloop.tools.runtime to avoid circular imports
# Re-export for backward compatibility using lazy import
def __getattr__(name: str):
    """Lazy import for ToolRuntime to avoid circular imports."""
    if name == "ToolRuntime":
        from atloop.tools.runtime import ToolRuntime

        return ToolRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Backward compatibility: re-export ToolResult from tools module
# Import lazily to avoid circular imports
def _get_tool_result():
    from atloop.tools.base import ToolResult

    return ToolResult


# For backward compatibility, import ToolResult directly
try:
    from atloop.tools.base import ToolResult
except ImportError:
    # Fallback if tools module not available
    from dataclasses import dataclass
    from typing import Any, Dict

    @dataclass
    class ToolResult:
        ok: bool
        stdout: str
        stderr: str
        exit_code: int
        meta: Dict[str, Any]


__all__ = [
    "ToolRuntime",  # Legacy - use ToolRegistry instead
    "ToolResult",
    "SandboxAdapter",
]
