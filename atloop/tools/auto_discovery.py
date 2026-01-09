"""Automatic tool discovery using AST parsing."""

import ast
import importlib
import inspect
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Type

from atloop.tools.base import BaseTool
from atloop.tools.tool_factory import ToolFactory

if TYPE_CHECKING:
    from atloop.runtime.sandbox_adapter import SandboxAdapter
    from atloop.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Python files in tools/ to exclude from discovery (infrastructure, not tools)
_EXCLUDED_FILES = frozenset({"__init__.py", "base.py", "registry.py", "auto_discovery.py"})


class ToolDiscovery:
    """Automatic tool discovery using AST and introspection."""

    def __init__(self, tools_dir: Optional[Path] = None):
        """
        Initialize tool discovery.

        Args:
            tools_dir: Directory containing tool modules (default: atloop/tools)
        """
        if tools_dir is None:
            # Default to atloop/tools directory
            tools_dir = Path(__file__).parent

        self.tools_dir = tools_dir
        self.base_tool_path = Path(__file__).parent / "base.py"

    def discover_tool_classes(self) -> List[Tuple[str, str, Type[BaseTool]]]:
        """
        Discover all tool classes by scanning Python files.

        Returns:
            List of tuples: (module_path, class_name, tool_class)
        """
        tool_classes = []

        # Scan all Python files in tools directory
        for py_file in self.tools_dir.rglob("*.py"):
            if py_file.name in _EXCLUDED_FILES:
                continue
            if "test" in py_file.name.lower():
                continue

            try:
                classes = self._extract_tool_classes_from_file(py_file)
                for class_name, tool_class in classes:
                    if (
                        inspect.isclass(tool_class)
                        and issubclass(tool_class, BaseTool)
                        and tool_class != BaseTool
                    ):
                        module_path = self._file_to_module_path(py_file)
                        tool_classes.append((module_path, class_name, tool_class))
            except Exception as e:
                logger.debug(f"[ToolDiscovery] Failed to scan {py_file}: {e}")
                continue

        return tool_classes

    def _file_to_module_path(self, file_path: Path) -> str:
        """
        Convert file path to module path.

        Args:
            file_path: Path to Python file

        Returns:
            Module path (e.g., "atloop.tools.filesystem.write_file")
        """
        abs_file_path = file_path.resolve()
        abs_tools_dir = self.tools_dir.resolve()

        # Find project root (where atloop/ directory is)
        # Start from tools_dir and go up until we find a directory containing 'atloop'
        project_root = abs_tools_dir.parent.parent  # atloop/tools -> atloop -> project_root

        # Try to get relative path from project root
        try:
            rel_path = abs_file_path.relative_to(project_root)
            # rel_path should be like: atloop/tools/filesystem/write_file.py
            parts = list(rel_path.parts)

            # Remove .py extension from filename
            if parts[-1].endswith(".py"):
                parts[-1] = parts[-1][:-3]

            # Convert to module path
            return ".".join(parts)
        except ValueError:
            # Fallback: use parts and find atloop
            parts = list(abs_file_path.parts)
            if "atloop" in parts:
                atloop_idx = parts.index("atloop")
                module_parts = parts[atloop_idx:]
                # Remove .py extension
                if module_parts[-1].endswith(".py"):
                    module_parts[-1] = module_parts[-1][:-3]
                return ".".join(module_parts)
            else:
                # Last resort: use filename without extension
                return file_path.stem

    def _extract_tool_classes_from_file(self, file_path: Path) -> List[Tuple[str, Type[BaseTool]]]:
        """
        Extract tool classes from a Python file using AST.

        Args:
            file_path: Path to Python file

        Returns:
            List of tuples: (class_name, tool_class)
        """
        # First, try to parse AST to find classes that inherit from BaseTool
        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(file_path))

            # Find classes that inherit from BaseTool
            tool_class_names = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if class inherits from BaseTool
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "BaseTool":
                            tool_class_names.append(node.name)
                        elif isinstance(base, ast.Attribute):
                            # Handle cases like atloop.tools.base.BaseTool
                            if base.attr == "BaseTool":
                                tool_class_names.append(node.name)

            if not tool_class_names:
                return []

            # Now import the module and get the actual classes
            module_path = self._file_to_module_path(file_path)
            try:
                module = importlib.import_module(module_path)
                classes = []
                for class_name in tool_class_names:
                    if hasattr(module, class_name):
                        cls = getattr(module, class_name)
                        if inspect.isclass(cls) and issubclass(cls, BaseTool) and cls != BaseTool:
                            classes.append((class_name, cls))
                return classes
            except ImportError as e:
                logger.debug(f"[ToolDiscovery] Failed to import {module_path}: {e}")
                return []

        except SyntaxError as e:
            logger.debug(f"[ToolDiscovery] Syntax error in {file_path}: {e}")
            return []
        except Exception as e:
            logger.debug(f"[ToolDiscovery] Error parsing {file_path}: {e}")
            return []

    def get_tool_info(self, tool_class: Type[BaseTool]) -> Dict[str, Any]:
        """
        Extract tool information from a tool class.

        Args:
            tool_class: Tool class

        Returns:
            Dictionary with tool information
        """
        info = {
            "class_name": tool_class.__name__,
            "module": tool_class.__module__,
            "docstring": inspect.getdoc(tool_class) or "",
        }

        # Get name and description by instantiating (with dummy args if needed)
        # We'll use introspection to get property values
        try:
            # Try to get name and description from class without instantiating
            # Check if they're defined as @property methods
            if hasattr(tool_class, "name"):
                name_prop = getattr(tool_class, "name")
                if isinstance(name_prop, property):
                    # Can't get property value without instance, but we can check the method
                    pass

            # Get __init__ signature to understand what parameters are needed
            init_sig = inspect.signature(tool_class.__init__)
            info["init_params"] = list(init_sig.parameters.keys())[1:]  # Skip 'self'
            info["init_signature"] = str(init_sig)
        except Exception as e:
            info["init_params"] = []
            info["init_signature"] = f"Error: {e}"

        return info

    def instantiate_tool(
        self, tool_class: Type[BaseTool], sandbox: "SandboxAdapter", skill_loader=None
    ) -> Optional[BaseTool]:
        """
        Instantiate a tool class with appropriate parameters.

        Delegates to ToolFactory for dependency injection.

        Args:
            tool_class: Tool class to instantiate
            sandbox: Sandbox adapter instance
            skill_loader: Optional skill loader instance

        Returns:
            Tool instance or None if instantiation fails
        """
        factory = ToolFactory(sandbox=sandbox, skill_loader=skill_loader)
        return factory.create(tool_class)


def auto_register_tools(
    registry: "ToolRegistry",
    sandbox: "SandboxAdapter",
    skill_loader=None,
    tools_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Automatically discover and register all tools.

    Args:
        registry: ToolRegistry instance
        sandbox: Sandbox adapter instance
        skill_loader: Optional skill loader instance
        tools_dir: Optional tools directory (default: atloop/tools)

    Returns:
        Dictionary with registration statistics
    """
    discovery = ToolDiscovery(tools_dir)
    tool_classes = discovery.discover_tool_classes()

    stats = {"discovered": len(tool_classes), "registered": 0, "failed": 0, "tools": []}

    for module_path, class_name, tool_class in tool_classes:
        try:
            # Instantiate tool
            tool_instance = discovery.instantiate_tool(tool_class, sandbox, skill_loader)
            if tool_instance:
                # Register tool
                registry.register(tool_instance)
                stats["registered"] += 1
                stats["tools"].append(
                    {"name": tool_instance.name, "class": class_name, "module": module_path}
                )
            else:
                stats["failed"] += 1
        except Exception as e:
            logger.warning(
                f"[ToolDiscovery] Failed to register {class_name} from {module_path}: {e}"
            )
            stats["failed"] += 1

    return stats
