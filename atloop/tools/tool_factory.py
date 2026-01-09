"""Tool factory for creating tool instances with dependency injection."""

import inspect
import logging
from typing import Any, Dict, Optional, Type

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolFactory:
    """Factory for creating tool instances with proper dependency injection."""

    def __init__(
        self,
        sandbox: SandboxAdapter,
        skill_loader=None,
    ):
        """
        Initialize tool factory.

        Args:
            sandbox: Sandbox adapter instance (required by most tools)
            skill_loader: Optional skill loader (required by skill-related tools)
        """
        self.sandbox = sandbox
        self.skill_loader = skill_loader

    def create(self, tool_class: Type[BaseTool]) -> Optional[BaseTool]:
        """
        Create a tool instance with appropriate dependencies.

        Automatically injects dependencies based on tool's __init__ signature:
        - If tool requires 'sandbox': injects self.sandbox
        - If tool requires 'skill_loader': injects self.skill_loader

        Args:
            tool_class: Tool class to instantiate

        Returns:
            Tool instance or None if instantiation fails
        """
        try:
            init_sig = inspect.signature(tool_class.__init__)
            params = list(init_sig.parameters.keys())[1:]  # Skip 'self'

            # Build arguments based on parameter names
            kwargs: Dict[str, Any] = {}
            if "sandbox" in params:
                kwargs["sandbox"] = self.sandbox
            if "skill_loader" in params:
                if self.skill_loader is None:
                    logger.debug(
                        f"[ToolFactory] Tool {tool_class.__name__} requires skill_loader "
                        f"but none provided, skipping"
                    )
                    return None
                kwargs["skill_loader"] = self.skill_loader

            # Instantiate
            instance = tool_class(**kwargs)
            logger.debug(f"[ToolFactory] Created {tool_class.__name__} instance")
            return instance
        except Exception as e:
            logger.debug(f"[ToolFactory] Failed to create {tool_class.__name__}: {e}")
            return None
