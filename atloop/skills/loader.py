"""Skill loader for loading and managing skills from SKILL.md files."""

import re
from pathlib import Path
from typing import Dict, Optional


class SkillLoader:
    """
    Loads and manages skills from SKILL.md files.

    A skill is a FOLDER containing:
    - SKILL.md (required): YAML frontmatter + markdown instructions
    - scripts/ (optional): Helper scripts the model can run
    - references/ (optional): Additional documentation
    - assets/ (optional): Templates, files for output

    SKILL.md Format:
    ----------------
        ---
        name: tool-usage
        description: Best practices for using tools effectively.
        ---

        # Tool Usage Skill

        ## Best Practices
        ...
    """

    def __init__(self, skills_dir: Path):
        """
        Initialize skill loader.

        Args:
            skills_dir: Directory containing skill folders
        """
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, dict] = {}
        self.load_skills()

    def parse_skill_md(self, path: Path) -> Optional[dict]:
        """
        Parse a SKILL.md file into metadata and body.

        Args:
            path: Path to SKILL.md file

        Returns:
            Dict with: name, description, body, path, dir
            None if file doesn't match format
        """
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return None

        # Match YAML frontmatter between --- markers
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return None

        frontmatter, body = match.groups()

        # Parse YAML-like frontmatter (simple key: value)
        metadata = {}
        for line in frontmatter.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip("\"'")

        # Require name and description
        if "name" not in metadata or "description" not in metadata:
            return None

        return {
            "name": metadata["name"],
            "description": metadata["description"],
            "body": body.strip(),
            "path": path,
            "dir": path.parent,
        }

    def load_skills(self):
        """
        Scan skills directory and load all valid SKILL.md files.

        Only loads metadata at startup - body is loaded on-demand.
        This keeps the initial context lean (Layer 1: ~100 tokens per skill).
        """
        if not self.skills_dir.exists():
            return

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            skill = self.parse_skill_md(skill_md)
            if skill:
                self.skills[skill["name"]] = skill

    def get_descriptions(self) -> str:
        """
        Generate skill descriptions for system prompt.

        This is Layer 1 - only name and description, ~100 tokens per skill.
        Full content (Layer 2) is loaded only when Skill tool is called.

        Returns:
            Formatted string with skill descriptions
        """
        if not self.skills:
            return "(no skills available)"

        return "\n".join(
            f"- {name}: {skill['description']}" for name, skill in sorted(self.skills.items())
        )

    def get_skill_content(self, name: str) -> Optional[str]:
        """
        Get full skill content for injection.

        This is Layer 2 - the complete SKILL.md body, plus any available
        resources (Layer 3 hints).

        Args:
            name: Skill name

        Returns:
            Full skill content string, or None if skill not found
        """
        if name not in self.skills:
            return None

        skill = self.skills[name]
        content = f"# Skill: {skill['name']}\n\n{skill['body']}"

        # List available resources (Layer 3 hints)
        resources = []
        for folder, label in [
            ("scripts", "Scripts"),
            ("references", "References"),
            ("assets", "Assets"),
        ]:
            folder_path = skill["dir"] / folder
            if folder_path.exists():
                files = list(folder_path.glob("*"))
                if files:
                    resources.append(f"{label}: {', '.join(f.name for f in files if f.is_file())}")

        if resources:
            content += f"\n\n**Available resources in {skill['dir']}:**\n"
            content += "\n".join(f"- {r}" for r in resources)

        return content

    def list_skills(self) -> list:
        """
        Return list of available skill names.

        Returns:
            List of skill names
        """
        return sorted(self.skills.keys())

    def has_skill(self, name: str) -> bool:
        """
        Check if a skill exists.

        Args:
            name: Skill name

        Returns:
            True if skill exists
        """
        return name in self.skills
