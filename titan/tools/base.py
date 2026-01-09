"""Base classes and types for tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """Result of tool execution."""

    ok: bool
    stdout: str
    stderr: str
    meta: Dict[str, Any]

    def __repr__(self) -> str:
        """String representation."""
        status = "✓" if self.ok else "✗"
        return f"ToolResult({status}, stdout_len={len(self.stdout)}, stderr_len={len(self.stderr)})"


class BaseTool(ABC):
    """Base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass

    @abstractmethod
    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """Execute tool with given arguments."""
        pass

    def needs_permission(self, args: Dict[str, Any]) -> bool:
        """Whether this tool needs user permission."""
        return False

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate tool arguments. Returns (is_valid, error_message)."""
        return True, None
