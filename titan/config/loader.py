"""Configuration loader using varlord (lib/api)."""

import logging
from pathlib import Path
from typing import Optional

from varlord import Config, sources
from varlord.global_config import get_global_config, set_global_config

from titan.config.models import TitanConfig

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Configuration loader - uses varlord for lib/api."""

    @staticmethod
    def setup(titan_dir: Optional[str] = None) -> Config:
        """
        Setup configuration - call once at application startup.
        
        Args:
            titan_dir: Custom Titan directory (for testing)
            
        Returns:
            Config instance (also registered globally)
        """
        logger.debug(f"[ConfigLoader] Setting up config with titan_dir: {titan_dir}")
        
        # Find Titan directory
        if titan_dir:
            titan_path = Path(titan_dir).resolve()
            logger.debug(f"[ConfigLoader] Using custom titan_dir: {titan_path}")
        else:
            # Check project .titan first
            project_titan = Path.cwd() / ".titan"
            if project_titan.exists() and project_titan.is_dir():
                titan_path = project_titan
                logger.debug(f"[ConfigLoader] Using project .titan: {titan_path}")
            else:
                titan_path = Path.home() / ".titan"
                logger.debug(f"[ConfigLoader] Using user .titan: {titan_path}")

        # Build sources list (lowest to highest priority)
        config_sources = []
        logger.debug(f"[ConfigLoader] Building config sources")

        # User config (lowest priority)
        user_config = Path.home() / ".titan" / "config" / "titan.yaml"
        if user_config.exists():
            config_sources.append(sources.YAML(str(user_config)))
            logger.debug(f"[ConfigLoader] Added user config: {user_config}")

        # Project config (higher priority)
        project_config = Path.cwd() / ".titan" / "config" / "titan.yaml"
        if project_config.exists() and project_config != titan_path / "config" / "titan.yaml":
            config_sources.append(sources.YAML(str(project_config)))
            logger.debug(f"[ConfigLoader] Added project config: {project_config}")

        # Custom titan_dir config (highest priority for files)
        if titan_dir:
            custom_config = titan_path / "config" / "titan.yaml"
            if custom_config.exists():
                config_sources.append(sources.YAML(str(custom_config)))
                logger.debug(f"[ConfigLoader] Added custom config: {custom_config}")

        # Environment variables
        config_sources.append(sources.Env(prefix="TITAN__"))
        logger.debug(f"[ConfigLoader] Added environment variables source")

        # .env file
        env_file = Path.cwd() / ".env"
        if env_file.exists():
            config_sources.append(sources.DotEnv(str(env_file)))
            logger.debug(f"[ConfigLoader] Added .env file: {env_file}")

        # Create configuration
        logger.debug(f"[ConfigLoader] Creating Config with {len(config_sources)} sources")
        cfg = Config(
            model=TitanConfig,
            sources=config_sources,
        )

        # Register globally
        set_global_config(cfg, name="titan")
        logger.info(f"[ConfigLoader] Configuration setup complete, registered globally")

        return cfg

    @staticmethod
    def get() -> TitanConfig:
        """
        Get configuration - access from anywhere in lib/api.
        
        Returns:
            Loaded TitanConfig instance (type-safe, validated against TitanConfig model)
            
        Raises:
            KeyError: If config not initialized (call setup() first)
            RequiredFieldError: If required fields missing (varlord validation)
            TypeError: If types don't match model (varlord validation)
        """
        logger.debug(f"[ConfigLoader] Getting config from global registry")
        config = get_global_config(name="titan")
        loaded_config = config.load()  # Validated against TitanConfig model
        logger.debug(f"[ConfigLoader] Config loaded: ai={loaded_config.ai.completion.model}")
        return loaded_config  # Type: TitanConfig (guaranteed by varlord)
