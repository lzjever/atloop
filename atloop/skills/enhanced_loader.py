"""Enhanced skill loader supporting multiple directories and user-defined skills."""

import re
from pathlib import Path
from typing import Dict, List, Optional


class EnhancedSkillLoader:
    """
    Enhanced skill loader supporting multiple directories with priority.

    Priority order (highest to lowest):
    1. Project skills: ./.atloop/skills/
    2. User skills: ~/.atloop/skills/
    3. Builtin skills: atloop/atloop/skills/builtin/
    """

    def __init__(
        self,
        builtin_skills_dir: Path,
        project_dir: Optional[Path] = None,
        additional_dirs: Optional[List[Path]] = None,
    ):
        """
        Initialize enhanced skill loader.

        Args:
            builtin_skills_dir: Directory containing builtin skills
            project_dir: Project root directory (for project skills)
            additional_dirs: Additional directories to load skills from (lowest priority)
        """
        self.builtin_skills_dir = Path(builtin_skills_dir)
        self.project_dir = Path(project_dir) if project_dir else None
        self.additional_dirs = [Path(d) for d in (additional_dirs or [])]

        # Determine user home directory
        self.user_skills_dir = Path.home() / ".atloop" / "skills"

        # Determine project skills directory
        if self.project_dir:
            self.project_skills_dir = self.project_dir / ".atloop" / "skills"
        else:
            self.project_skills_dir = None

        # Load skills with priority
        self.skills: Dict[str, dict] = {}
        self.skill_sources: Dict[str, str] = {}  # Track source of each skill
        self.load_all_skills()

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

    def load_skills_from_dir(self, skills_dir: Path, source: str) -> int:
        """
        Load skills from a directory.

        Args:
            skills_dir: Directory containing skill folders
            source: Source identifier (e.g., "builtin", "user", "project")

        Returns:
            Number of skills loaded
        """
        if not skills_dir.exists():
            return 0

        count = 0
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                # Also check for lowercase skill.md
                skill_md = skill_dir / "skill.md"
                if not skill_md.exists():
                    continue

            skill = self.parse_skill_md(skill_md)
            if skill:
                skill_name = skill["name"]
                # Only add if not already loaded (priority: project > user > builtin)
                if skill_name not in self.skills:
                    self.skills[skill_name] = skill
                    self.skill_sources[skill_name] = source
                    count += 1

        return count

    def load_all_skills(self):
        """
        Load skills from directories in priority order.

        Priority: project > user > builtin
        Later sources override earlier ones with the same name.
        """
        # Load in reverse priority order (builtin first, then user, then project)
        # This ensures project skills override user skills, which override builtin skills

        # 1. Builtin skills (lowest priority, always loaded)
        if self.builtin_skills_dir.exists():
            self.load_skills_from_dir(self.builtin_skills_dir, "builtin")

        # 2. User skills (medium priority)
        # Always load user skills (they will be overridden by project skills if same name)
        if self.user_skills_dir.exists():
            self.load_skills_from_dir(self.user_skills_dir, "user")

        # 3. Project skills (highest priority)
        # Project skills will override user/builtin skills with the same name
        if self.project_skills_dir and self.project_skills_dir.exists():
            self.load_skills_from_dir(self.project_skills_dir, "project")

        # 4. Additional directories (lowest priority, loaded in order)
        for i, additional_dir in enumerate(self.additional_dirs):
            if additional_dir.exists():
                self.load_skills_from_dir(additional_dir, f"additional_{i}")

    def get_descriptions(self) -> str:
        """
        Generate skill descriptions for system prompt.

        Returns:
            Formatted string with skill descriptions
        """
        if not self.skills:
            return "(no skills available)"

        lines = []
        for name, skill in sorted(self.skills.items()):
            source = self.skill_sources.get(name, "unknown")
            lines.append(f"- {name}: {skill['description']} (from {source})")

        return "\n".join(lines)

    def get_skill_content(self, name: str) -> Optional[str]:
        """
        Get full skill content for injection.

        Args:
            name: Skill name

        Returns:
            Full skill content string, or None if skill not found
        """
        if name not in self.skills:
            return None

        skill = self.skills[name]
        source = self.skill_sources.get(name, "unknown")
        content = f"# Skill: {skill['name']} (from {source})\n\n{skill['body']}"

        # List available resources
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

    def list_skills(self) -> List[str]:
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

    def get_skill_source(self, name: str) -> Optional[str]:
        """
        Get the source of a skill.

        Args:
            name: Skill name

        Returns:
            Source identifier or None if skill not found
        """
        return self.skill_sources.get(name)

    def get_skill_script_path(self, name: str, script_name: str) -> Optional[Path]:
        """
        Get path to a script in a skill's scripts directory.

        Args:
            name: Skill name
            script_name: Script filename

        Returns:
            Path to script, or None if not found
        """
        if name not in self.skills:
            return None

        skill = self.skills[name]
        script_path = skill["dir"] / "scripts" / script_name

        if script_path.exists() and script_path.is_file():
            return script_path

        return None

    def get_skill_resource_path(
        self, name: str, resource_type: str, resource_name: str
    ) -> Optional[Path]:
        """
        Get path to a resource in a skill's resource directory.

        Args:
            name: Skill name
            resource_type: Type of resource ("references" or "assets")
            resource_name: Resource filename

        Returns:
            Path to resource, or None if not found
        """
        if name not in self.skills:
            return None

        if resource_type not in ["references", "assets"]:
            return None

        skill = self.skills[name]
        resource_path = skill["dir"] / resource_type / resource_name

        if resource_path.exists():
            return resource_path

        return None
