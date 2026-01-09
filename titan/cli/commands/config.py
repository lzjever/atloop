"""Config command - show configuration."""

import logging
import sys
from typing import Any

from titan.config.loader import ConfigLoader

logger = logging.getLogger(__name__)


def cmd_config(args: Any) -> int:
    """Show configuration - single method."""
    logger.debug(f"[CLI] Config command called with args: {vars(args)}")
    
    try:
        titan_dir = getattr(args, "titan_dir", None)
        logger.debug(f"[CLI] Loading config with titan_dir: {titan_dir}")
        
        # Setup and get config
        ConfigLoader.setup(titan_dir=titan_dir)
        config = ConfigLoader.get()
        
        print("TITAN Configuration:")
        print(f"  Completion API: {config.ai.completion.api_base}")
        print(f"  Completion Model: {config.ai.completion.model}")
        print(f"  Max Tokens Input: {config.ai.performance.max_tokens_input}")
        print(f"  Max Tokens Output: {config.ai.performance.max_tokens_output}")
        if config.sandbox.base_url:
            print(f"  Sandbox URL: {config.sandbox.base_url}")
        if config.skills_dirs:
            print(f"  Skills Dirs: {', '.join(config.skills_dirs)}")
        if config.mcp_config_path:
            print(f"  MCP Config: {config.mcp_config_path}")
        
        return 0
    except Exception as e:
        logger.error(f"[CLI] Config command failed: {e}")
        logger.debug(f"[CLI] Exception details: {type(e).__name__}: {e}", exc_info=True)
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
