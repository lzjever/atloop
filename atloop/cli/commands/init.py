"""Init command - initialize configuration."""

import logging
import sys
from typing import Any

from atloop.config.loader import ConfigLoader

logger = logging.getLogger(__name__)


def cmd_init(args: Any) -> int:
    """Initialize configuration - single method."""
    logger.debug(f"[CLI] Init command called with args: {vars(args)}")

    try:
        atloop_dir = getattr(args, "atloop_dir", None)
        logger.debug(f"[CLI] Initializing config with atloop_dir: {atloop_dir}")

        # Setup config
        ConfigLoader.setup(atloop_dir=atloop_dir)
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
