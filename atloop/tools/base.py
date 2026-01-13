"""Base classes and types for tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from atloop.tools.output_semantic_type import OutputSemanticType


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
    """Base class for all tools.

    Tools can declare their output semantic types to enable automatic
    application of appropriate output size limits.
    """

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

    @property
    def output_semantic_type(self) -> OutputSemanticType:
        """Return the semantic type of tool output.

        Default: STATUS_MESSAGE (suitable for most tools that return
        simple success/failure messages).

        Subclasses can override this property to declare their output
        semantic type.

        Returns:
            OutputSemanticType enum value
        """
        return OutputSemanticType.STATUS_MESSAGE

    @property
    def stdout_semantic_type(self) -> OutputSemanticType:
        """Return the semantic type of stdout output.

        Default: Uses output_semantic_type.

        Subclasses can override this if stdout has a different semantic
        type than the general output.

        Returns:
            OutputSemanticType enum value
        """
        return self.output_semantic_type

    @property
    def stderr_semantic_type(self) -> OutputSemanticType:
        """Return the semantic type of stderr output.

        Default: ERROR_MESSAGE (stderr is typically error information).

        Subclasses can override this if stderr has a different semantic type.

        Returns:
            OutputSemanticType enum value
        """
        return OutputSemanticType.ERROR_MESSAGE

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
