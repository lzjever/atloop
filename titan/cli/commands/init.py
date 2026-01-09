"""Init command - initialize configuration."""

import logging
import sys
from pathlib import Path
from typing import Any

from titan.config.loader import ConfigLoader

logger = logging.getLogger(__name__)


def cmd_init(args: Any) -> int:
    """Initialize configuration - single method."""
    logger.debug(f"[CLI] Init command called with args: {vars(args)}")
    
    try:
        titan_dir = getattr(args, "titan_dir", None)
        logger.debug(f"[CLI] Initializing config with titan_dir: {titan_dir}")
        
        # Setup config
        ConfigLoader.setup(titan_dir=titan_dir)
        config = ConfigLoader.get()
        
        print("Configuration initialized successfully")
        print(f"  Completion API: {config.ai.completion.api_base}")
        print(f"  Completion Model: {config.ai.completion.model}")
        
        return 0
    except Exception as e:
        logger.error(f"[CLI] Init command failed: {e}")
        logger.debug(f"[CLI] Exception details: {type(e).__name__}: {e}", exc_info=True)
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
