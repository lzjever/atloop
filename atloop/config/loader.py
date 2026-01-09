"""Configuration loader using varlord (lib/api)."""

import logging
from pathlib import Path
from typing import Optional

from varlord import Config, sources
from varlord.global_config import get_global_config, set_global_config

from atloop.config.models import AtloopConfig

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Configuration loader - uses varlord for lib/api."""

    @staticmethod
    def setup(atloop_dir: Optional[str] = None) -> Config:
        """
        Setup configuration - call once at application startup.

        Args:
            atloop_dir: Custom atloop directory (for testing)

        Returns:
            Config instance (also registered globally)
        """
        logger.debug(f"[ConfigLoader] Setting up config with atloop_dir: {atloop_dir}")

        # Find atloop directory
        if atloop_dir:
            atloop_path = Path(atloop_dir).resolve()
            logger.debug(f"[ConfigLoader] Using custom atloop_dir: {atloop_path}")
        else:
            # Check project .atloop first
            project_atloop = Path.cwd() / ".atloop"
            if project_atloop.exists() and project_atloop.is_dir():
                atloop_path = project_atloop
                logger.debug(f"[ConfigLoader] Using project .atloop: {atloop_path}")
            else:
                atloop_path = Path.home() / ".atloop"
                logger.debug(f"[ConfigLoader] Using user .atloop: {atloop_path}")

        # Build sources list (lowest to highest priority)
        config_sources = []
        logger.debug("[ConfigLoader] Building config sources")

        # User config (lowest priority)
        user_config = Path.home() / ".atloop" / "config" / "atloop.yaml"
        if user_config.exists():
            config_sources.append(sources.YAML(str(user_config)))
            logger.debug(f"[ConfigLoader] Added user config: {user_config}")

        # Project config (higher priority)
        project_config = Path.cwd() / ".atloop" / "config" / "atloop.yaml"
        if project_config.exists() and project_config != atloop_path / "config" / "atloop.yaml":
            config_sources.append(sources.YAML(str(project_config)))
            logger.debug(f"[ConfigLoader] Added project config: {project_config}")

        # Custom atloop_dir config (highest priority for files)
        if atloop_dir:
            custom_config = atloop_path / "config" / "atloop.yaml"
            if custom_config.exists():
                config_sources.append(sources.YAML(str(custom_config)))
                logger.debug(f"[ConfigLoader] Added custom config: {custom_config}")

        # Environment variables
        config_sources.append(sources.Env(prefix="ATLOOP__"))
        logger.debug("[ConfigLoader] Added environment variables source")

        # .env file
        env_file = Path.cwd() / ".env"
        if env_file.exists():
            config_sources.append(sources.DotEnv(str(env_file)))
            logger.debug(f"[ConfigLoader] Added .env file: {env_file}")

        # Create configuration
        logger.debug(f"[ConfigLoader] Creating Config with {len(config_sources)} sources")
        cfg = Config(
            model=AtloopConfig,
            sources=config_sources,
        )

        # Register globally
        set_global_config(cfg, name="atloop")
        logger.info("[ConfigLoader] Configuration setup complete, registered globally")

        return cfg

    @staticmethod
    def get() -> AtloopConfig:
        """
        Get configuration - access from anywhere in lib/api.

        Returns:
            Loaded AtloopConfig instance (type-safe, validated against AtloopConfig model)

        Raises:
            KeyError: If config not initialized (call setup() first)
            RequiredFieldError: If required fields missing (varlord validation)
            TypeError: If types don't match model (varlord validation)
        """
        logger.debug("[ConfigLoader] Getting config from global registry")
        config = get_global_config(name="atloop")
        loaded_config = config.load()  # Validated against AtloopConfig model
        logger.debug(f"[ConfigLoader] Config loaded: ai={loaded_config.ai.completion.model}")
        return loaded_config  # Type: AtloopConfig (guaranteed by varlord)
