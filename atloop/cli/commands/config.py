"""Config command - show configuration."""

import logging
import sys
from typing import Any

from atloop.config.loader import ConfigLoader

logger = logging.getLogger(__name__)


def cmd_config(args: Any) -> int:
    """Show configuration - single method."""
    logger.debug(f"[CLI] Config command called with args: {vars(args)}")

    try:
        atloop_dir = getattr(args, "atloop_dir", None)
        logger.debug(f"[CLI] Loading config with atloop_dir: {atloop_dir}")

        # Setup and get config
        ConfigLoader.setup(atloop_dir=atloop_dir)
        config = ConfigLoader.get()

        from pathlib import Path

        atloop_dir = ConfigLoader.get_atloop_dir()
        skills_dirs = [atloop_dir / "skills", Path.home() / ".atloop" / "skills"]
        skills_dirs = [str(d) for d in skills_dirs if d.exists()]
        mcp_config_path = atloop_dir / "mcp.json"

        print("atloop Configuration:")
        print(f"  Completion API: {config.ai.completion.api_base}")
        print(f"  Completion Model: {config.ai.completion.model}")
        print(f"  Max Tokens Input: {config.ai.performance.max_tokens_input}")
        print(f"  Max Tokens Output: {config.ai.performance.max_tokens_output}")
        if config.sandbox.base_url:
            print(f"  Sandbox URL: {config.sandbox.base_url}")
        if skills_dirs:
            print(f"  Skills Dirs: {', '.join(skills_dirs)}")
        if mcp_config_path.exists():
            print(f"  MCP Config: {mcp_config_path}")

        return 0
    except Exception as e:
        logger.error(f"[CLI] Config command failed: {e}")
        logger.debug(f"[CLI] Exception details: {type(e).__name__}: {e}", exc_info=True)
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1
