"""Tool registry for managing and executing tools."""

import logging
from typing import Any, Dict, List, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.auto_discovery import auto_register_tools
from atloop.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self, sandbox: SandboxAdapter, skill_loader=None):
        """
        Initialize tool registry.

        Args:
            sandbox: Sandbox adapter instance (required by run, read_file, write_file, etc.)
            skill_loader: Optional skill loader for read_skill_file and skill tools.
                Passed automatically to tools that declare skill_loader in __init__.
        """
        self.sandbox = sandbox
        self.skill_loader = skill_loader
        self.tools: Dict[str, BaseTool] = {}
        self._registration_stats: Dict[str, Any] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """
        Register builtin tools using automatic discovery.

        This is called during initialization. Registration failures are logged
        but do not prevent registry creation (some tools may be optional).
        """
        try:
            stats = auto_register_tools(
                registry=self, sandbox=self.sandbox, skill_loader=self.skill_loader
            )
            self._registration_stats = stats

            logger.info(
                f"[ToolRegistry] Auto-discovered {stats['discovered']} tools, "
                f"registered {stats['registered']}, failed {stats['failed']}"
            )

            if stats["registered"] > 0:
                tool_names = [t["name"] for t in stats["tools"]]
                logger.info(f"[ToolRegistry] Registered tools: {', '.join(sorted(tool_names))}")

            if stats["failed"] > 0:
                logger.warning(
                    f"[ToolRegistry] Failed to register {stats['failed']} tool(s). "
                    f"Some tools may not be available."
                )

        except Exception as e:
            logger.error(
                f"[ToolRegistry] Auto-discovery failed: {e}",
                exc_info=True,
            )
            self._registration_stats = {
                "discovered": 0,
                "registered": 0,
                "failed": 0,
                "tools": [],
                "error": str(e),
            }
            logger.warning(
                f"[ToolRegistry] Tool registration failed. "
                f"Registry created but no tools available. Error: {e}"
            )

    def register(self, tool: BaseTool):
        """Register a tool."""
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self.tools.keys())

    def get_registration_stats(self) -> Dict[str, Any]:
        """
        Get tool registration statistics.

        Returns:
            Dictionary with registration stats (discovered, registered, failed, tools)
        """
        return self._registration_stats.copy()

    def execute(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            ToolResult instance

        Raises:
            ValueError: If tool not found
        """
        tool = self.get(tool_name)
        if not tool:
            return ToolResult(
                ok=False,
                stdout="",
                stderr=f"Unknown tool: {tool_name}. Available tools: {', '.join(self.list_tools())}",
                meta={"tool": tool_name},
            )

        # Validate arguments
        is_valid, error = tool.validate_args(args)
        if not is_valid:
            return ToolResult(
                ok=False,
                stdout="",
                stderr=error or f"Invalid arguments for tool: {tool_name}",
                meta={"tool": tool_name, "args": args},
            )

        # Execute tool
        return tool.execute(args)
