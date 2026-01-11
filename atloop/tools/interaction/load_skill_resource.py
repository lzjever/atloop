"""Load skill resource tool for incrementally loading resource files into memory cache."""

from typing import Any, Dict, Optional

from atloop.tools.base import BaseTool, ToolResult
from atloop.tools.output_semantic_type import OutputSemanticType


class LoadSkillResourceTool(BaseTool):
    """
    Tool for incrementally loading resource files from a skill into memory cache.
    
    This tool loads a specific resource file (script, reference, or asset) from
    a skill and caches it in memory. The cached content will be available in
    future memory summaries. Use this tool after `load_skill` to load specific
    resources that you need.
    
    **Use cases:**
    - Loading specific scripts when needed
    - Loading reference documentation on demand
    - Reducing token consumption by loading only needed resources
    """

    def __init__(self, skill_loader=None):
        """
        Initialize load skill resource tool.
        
        Args:
            skill_loader: SkillLoader or EnhancedSkillLoader instance
        """
        self.skill_loader = skill_loader

    @property
    def name(self) -> str:
        """Tool name."""
        return "load_skill_resource"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Load a specific resource file from a skill into memory cache. The resource "
            "content will be cached and available in future memory summaries. Use this "
            "tool after `load_skill` to load specific scripts, references, or assets "
            "that you need. The content is cached, so you don't need to reload it."
        )

    @property
    def output_semantic_type(self) -> OutputSemanticType:
        """Return semantic type: KNOWLEDGE_CONTENT."""
        return OutputSemanticType.KNOWLEDGE_CONTENT

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "skill_name" not in args:
            return False, "Missing required argument: 'skill_name'"
        if not isinstance(args.get("skill_name"), str):
            return False, "Argument 'skill_name' must be a string"
        if "resource_type" not in args:
            return False, "Missing required argument: 'resource_type'"
        if args.get("resource_type") not in ["scripts", "references", "assets"]:
            return False, "Argument 'resource_type' must be one of: scripts, references, assets"
        if "resource_name" not in args:
            return False, "Missing required argument: 'resource_name'"
        if not isinstance(args.get("resource_name"), str):
            return False, "Argument 'resource_name' must be a string"
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Load a specific resource file and cache it in memory.
        
        Args:
            args: Must contain:
                - skill_name (str): Skill name
                - resource_type (str): "scripts", "references", or "assets"
                - resource_name (str): Resource file name
        
        Returns:
            ToolResult with confirmation message (resource content is cached, not returned)
        """
        skill_name = args["skill_name"]
        resource_type = args["resource_type"]
        resource_name = args["resource_name"]

        if not self.skill_loader:
            return ToolResult(
                ok=False,
                stdout="",
                stderr="Skill loader not available. Cannot load resource.",
                meta={
                    "skill_name": skill_name,
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                },
            )

        # Load resource content
        content = self.skill_loader.load_skill_resource(
            skill_name, resource_type, resource_name
        )

        if content is None:
            # Try to get available resources for better error message
            skill_data = self.skill_loader.get_skill_metadata_and_resources(skill_name)
            if skill_data is None:
                return ToolResult(
                    ok=False,
                    stdout="",
                    stderr=f"Skill '{skill_name}' not found.",
                    meta={
                        "skill_name": skill_name,
                        "resource_type": resource_type,
                        "resource_name": resource_name,
                    },
                )
            
            available = skill_data["resources"].get(resource_type, [])
            available_str = f" Available {resource_type}: {', '.join(available)}" if available else f" No {resource_type} available for this skill."
            
            return ToolResult(
                ok=False,
                stdout="",
                stderr=(
                    f"Resource '{resource_name}' not found in {resource_type} for skill '{skill_name}'.{available_str}"
                ),
                meta={
                    "skill_name": skill_name,
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                },
            )

        # Return confirmation message (content is cached in memory, not returned here)
        # The actual caching is handled by ActPhase
        output = f"""Resource loaded into skill cache.

**Skill**: {skill_name}
**Resource Type**: {resource_type}
**Resource Name**: {resource_name}
**Content Length**: {len(content)} characters

**Note**: This resource is now cached in memory. It will be available in future memory summaries.
You can access the cached content through the memory summary."""

        return ToolResult(
            ok=True,
            stdout=output,
            stderr="",
            meta={
                "skill_name": skill_name,
                "resource_type": resource_type,
                "resource_name": resource_name,
                "content_length": len(content),
                "cached": True,
                # Store content in meta for caching (will be extracted by ActPhase)
                "_content": content,
            },
        )
