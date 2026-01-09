"""Tool runtime module."""

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.runtime.tool_runtime import ToolRuntime  # Legacy compatibility


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
