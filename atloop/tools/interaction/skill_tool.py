"""Skill tool for loading skill knowledge on-demand."""

from typing import Any, Dict, Optional

from atloop.tools.base import BaseTool, ToolResult


class SkillTool(BaseTool):
    """
    Tool for loading skill content on-demand.

    When the LLM needs guidance from a skill (e.g., tool-usage, error-handling),
    it uses this tool to load the full skill content. The skill content is returned
    as stdout for the LLM to read and apply.

    **Use cases:**
    - Loading tool usage best practices (tool-usage skill)
    - Loading error handling guidance (error-handling skill)
    - Loading domain-specific knowledge (any custom skill)

    **Note:** This tool requires skill_loader to be configured in the ToolRegistry.
    """

    def __init__(self, skill_loader=None):
        """
        Initialize skill tool.

        Args:
            skill_loader: SkillLoader or EnhancedSkillLoader instance for loading skill content
        """
        self.skill_loader = skill_loader

    @property
    def name(self) -> str:
        """Tool name."""
        return "skill"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Load skill knowledge on-demand. Use when task matches a skill's description (e.g., tool-usage, error-handling). Returns the full skill content as guidance."

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "name" not in args:
            return False, "Missing required argument: 'name' (skill name)"
        if not isinstance(args.get("name"), str):
            return False, "Argument 'name' must be a string"
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Load and return skill content.

        Args:
            args: Must contain 'name' (str) - the skill name to load

        Returns:
            ToolResult with skill content in stdout, or error in stderr
        """
        skill_name = args["name"]

        if not self.skill_loader:
            return ToolResult(
                ok=False,
                stdout="",
                stderr="Skill loader not available. Cannot load skill content.",
                meta={"skill_name": skill_name},
            )

        content = self.skill_loader.get_skill_content(skill_name)

        if content is None or content == "":
            available = ""
            if hasattr(self.skill_loader, "skills") and self.skill_loader.skills:
                available = f" Available skills: {', '.join(self.skill_loader.skills.keys())}"
            return ToolResult(
                ok=False,
                stdout="",
                stderr=f"Skill '{skill_name}' not found or has no content.{available}",
                meta={"skill_name": skill_name},
            )

        return ToolResult(
            ok=True,
            stdout=content,
            stderr="",
            meta={"skill_name": skill_name, "content_length": len(content)},
        )
