"""Prompt templates package."""

from pathlib import Path


class PromptLoader:
    """Prompt loader - supports language switching."""

    def __init__(self, language: str = "en"):
        """
        Initialize prompt loader.

        Args:
            language: Language code ("en" or "zh")
        """
        self.language = language
        self.prompt_dir = Path(__file__).parent / language

    def load(self, template_name: str) -> str:
        """
        Load prompt template.

        Args:
            template_name: Template name (without extension)

        Returns:
            Template content
        """
        template_path = self.prompt_dir / f"{template_name}.txt"
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        return template_path.read_text(encoding="utf-8")

    def set_language(self, language: str) -> None:
        """Set language."""
        if language not in ["en", "zh"]:
            raise ValueError(f"Unsupported language: {language}")
        self.language = language
        self.prompt_dir = Path(__file__).parent / language
