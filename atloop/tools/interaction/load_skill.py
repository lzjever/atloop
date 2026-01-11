"""Load skill tool for loading skill metadata and resource list."""

from typing import Any, Dict, Optional

from atloop.tools.base import BaseTool, ToolResult
from atloop.tools.output_semantic_type import OutputSemanticType


class LoadSkillTool(BaseTool):
    """
    Tool for loading skill metadata and resource list (without resource content).
    
    This tool loads the skill's main content (SKILL.md body) and lists available
    resource files (scripts, references, assets) without loading their content.
    Use this tool first to explore a skill's capabilities, then use
    `load_skill_resource` to incrementally load specific resource files when needed.
    
    **Use cases:**
    - Exploring available skills
    - Getting skill guidance without loading all resources
    - Reducing initial token consumption
    """

    def __init__(self, skill_loader=None):
        """
        Initialize load skill tool.
        
        Args:
            skill_loader: SkillLoader or EnhancedSkillLoader instance
        """
        self.skill_loader = skill_loader

    @property
    def name(self) -> str:
        """Tool name."""
        return "load_skill"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Load skill metadata and resource list. Returns the skill's main content "
            "(SKILL.md body) and a list of available resource files (scripts, references, "
            "assets) without their contents. Use this tool first to explore a skill's "
            "capabilities. Then use `load_skill_resource` to incrementally load specific "
            "resource files when needed."
        )

    @property
    def output_semantic_type(self) -> OutputSemanticType:
        """Return semantic type: KNOWLEDGE_CONTENT."""
        return OutputSemanticType.KNOWLEDGE_CONTENT

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "name" not in args:
            return False, "Missing required argument: 'name' (skill name)"
        if not isinstance(args.get("name"), str):
            return False, "Argument 'name' must be a string"
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Load skill metadata and resource list.
        
        Args:
            args: Must contain 'name' (str) - the skill name to load
        
        Returns:
            ToolResult with skill metadata and resource list in stdout
        """
        skill_name = args["name"]

        if not self.skill_loader:
            return ToolResult(
                ok=False,
                stdout="",
                stderr="Skill loader not available. Cannot load skill.",
                meta={"skill_name": skill_name},
            )

        # Get metadata and resources (without resource content)
        skill_data = self.skill_loader.get_skill_metadata_and_resources(skill_name)

        if skill_data is None:
            available = ""
            if hasattr(self.skill_loader, "list_skills"):
                available_skills = self.skill_loader.list_skills()
                if available_skills:
                    available = f" Available skills: {', '.join(available_skills)}"
            return ToolResult(
                ok=False,
                stdout="",
                stderr=f"Skill '{skill_name}' not found.{available}",
                meta={"skill_name": skill_name},
            )

        metadata = skill_data["metadata"]
        resources = skill_data["resources"]

        # Build output with main content and resource list
        parts = []
        parts.append(f"# Skill: {metadata['name']}")
        if "source" in metadata:
            parts.append(f"**Source**: {metadata['source']}")
        parts.append("")
        parts.append("## Description")
        parts.append(metadata["description"])
        parts.append("")
        parts.append("## Main Content")
        parts.append(metadata["body"])
        parts.append("")

        # List available resources
        has_resources = any(resources.values())
        if has_resources:
            parts.append("## Available Resources")
            parts.append("")
            parts.append(
                "**Note**: Use `load_skill_resource` to load specific resource files when needed."
            )
            parts.append("")

            for resource_type, file_names in resources.items():
                if file_names:
                    parts.append(f"### {resource_type.capitalize()}")
                    for file_name in file_names:
                        parts.append(f"- {file_name}")
                    parts.append("")
        else:
            parts.append("## Available Resources")
            parts.append("No additional resources available for this skill.")
            parts.append("")

        output = "\n".join(parts)

        return ToolResult(
            ok=True,
            stdout=output,
            stderr="",
            meta={
                "skill_name": skill_name,
                "resources": resources,
                "content_length": len(output),
            },
        )
