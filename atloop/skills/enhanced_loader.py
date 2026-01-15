"""Enhanced skill loader supporting multiple directories and user-defined skills."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EnhancedSkillLoader:
    """Skill loader supporting multiple directories with priority: project > user > builtin."""

    def __init__(
        self,
        builtin_skills_dir: Path,
        project_dir: Optional[Path] = None,
        additional_dirs: Optional[List[Path]] = None,
    ):
        """Initialize skill loader."""
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
        """Parse a SKILL.md file into metadata and body."""
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, FileNotFoundError):
            # File read failed (permissions, encoding, not found)
            return None

        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return None

        frontmatter, body = match.groups()

        metadata = {}
        for line in frontmatter.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip("\"'")

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
        """Load skills from a directory."""
        if not skills_dir.exists():
            return 0

        count = 0
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                skill_md = skill_dir / "skill.md"
                if not skill_md.exists():
                    continue

            skill = self.parse_skill_md(skill_md)
            if skill:
                skill_name = skill["name"]
                if skill_name not in self.skills:
                    self.skills[skill_name] = skill
                    self.skill_sources[skill_name] = source
                    count += 1

        return count

    def load_all_skills(self):
        """Load skills from directories in priority order: project > user > builtin."""
        if self.builtin_skills_dir.exists():
            self.load_skills_from_dir(self.builtin_skills_dir, "builtin")

        if self.user_skills_dir.exists():
            self.load_skills_from_dir(self.user_skills_dir, "user")

        if self.project_skills_dir and self.project_skills_dir.exists():
            self.load_skills_from_dir(self.project_skills_dir, "project")

        for i, additional_dir in enumerate(self.additional_dirs):
            if additional_dir.exists():
                self.load_skills_from_dir(additional_dir, f"additional_{i}")

    def get_descriptions(self) -> str:
        """Generate skill descriptions for system prompt."""
        if not self.skills:
            return "(no skills available)"

        lines = []
        for name, skill in sorted(self.skills.items()):
            source = self.skill_sources.get(name, "unknown")
            lines.append(f"- {name}: {skill['description']} (from {source})")

        return "\n".join(lines)

    def list_skills(self) -> List[str]:
        """Return list of available skill names."""
        return sorted(self.skills.keys())

    def has_skill(self, name: str) -> bool:
        """Check if a skill exists."""
        return name in self.skills

    def get_skill_source(self, name: str) -> Optional[str]:
        """Get the source of a skill."""
        return self.skill_sources.get(name)

    def get_skill_metadata_and_resources(self, name: str) -> Optional[Dict[str, Any]]:
        """Get skill metadata and resource list (without resource content)."""
        if name not in self.skills:
            return None

        skill = self.skills[name]
        source = self.skill_sources.get(name, "unknown")

        metadata = {
            "name": skill["name"],
            "description": skill["description"],
            "body": skill["body"],
            "source": source,
            "dir": str(skill["dir"]),
        }

        resources = {"scripts": [], "references": [], "assets": []}

        for folder, key in [
            ("scripts", "scripts"),
            ("references", "references"),
            ("assets", "assets"),
        ]:
            folder_path = skill["dir"] / folder
            if folder_path.exists():
                files = [f.name for f in folder_path.glob("*") if f.is_file()]
                resources[key] = sorted(files)

        return {"metadata": metadata, "resources": resources}

    def load_skill_resource(
        self, skill_name: str, resource_type: str, resource_name: str
    ) -> Optional[str]:
        """Load a specific resource file content from a skill."""
        if skill_name not in self.skills or resource_type not in [
            "scripts",
            "references",
            "assets",
        ]:
            return None

        skill = self.skills[skill_name]
        resource_path = skill["dir"] / resource_type / resource_name

        if not resource_path.exists() or not resource_path.is_file():
            return None

        try:
            return resource_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"[EnhancedSkillLoader] Failed to read resource {resource_name}: {e}")
            return None
