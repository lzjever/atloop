"""Exec command - execute task with prompt string."""

import logging
import os
import sys
from pathlib import Path
from typing import Any

from atloop.api.runner import TaskRunner
from atloop.output.emitter import OutputEventEmitter
from atloop.output.console.handler import ConsoleOutputHandler

logger = logging.getLogger(__name__)


def cmd_exec(args: Any) -> int:
    """Execute task with prompt string."""
    logger.debug(f"[CLI] Exec command called with args: {vars(args)}")

    try:
        # Read prompt from positional argument or stdin
        if args.prompt:
            prompt = args.prompt
            logger.debug(f"[CLI] Using prompt from command line (length: {len(prompt)})")
        else:
            # Read from stdin
            prompt = sys.stdin.read().strip()
            if not prompt:
                print("Error: No prompt provided. Either provide as argument or via stdin.", file=sys.stderr)
                return 1
            logger.debug(f"[CLI] Loaded prompt from stdin (length: {len(prompt)})")

        # Get workspace_root from config (defaults to current directory if not set)
        from atloop.config.loader import ConfigLoader

        config = ConfigLoader.get()
        workspace_root = config.runtime.workspace_root
        if workspace_root is None:
            workspace_root = str(Path.cwd())
            logger.debug(f"[CLI] No workspace_root in config, using current directory: {workspace_root}")
        else:
            workspace_root = str(Path(workspace_root).resolve())
            logger.debug(f"[CLI] Using workspace_root from config: {workspace_root}")

        # Create workspace if it doesn't exist
        workspace_path = Path(workspace_root)
        if not workspace_path.exists():
            workspace_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"[CLI] Created workspace: {workspace_path}")

        # Get upload_workspace from config
        upload_workspace = config.runtime.upload_workspace
        logger.debug(f"[CLI] Upload workspace: {upload_workspace}")

        # Setup console output handler
        output_format = (
            getattr(args, "output_format", "minimal")
            or os.getenv("ATLOOP_OUTPUT_FORMAT", "minimal")
        )
        event_emitter = OutputEventEmitter()
        console_handler = ConsoleOutputHandler(output_format=output_format, enabled=True)
        event_emitter.subscribe(console_handler.handle)
        console_handler.start()

        try:
            # Execute
            runner = TaskRunner(atloop_dir=getattr(args, "atloop_dir", None))
            logger.debug("[CLI] Starting task execution")
            result = runner.execute(goal=prompt, workspace_root=workspace_root, upload_workspace=upload_workspace)
            logger.debug(f"[CLI] Task execution completed: success={result['success']}")

            return 0 if result["success"] else 1
        finally:
            # Cleanup
            console_handler.stop()
            event_emitter.unsubscribe(console_handler.handle)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error(f"[CLI] Exec command failed: {e}")
        logger.debug(f"[CLI] Exception details: {type(e).__name__}: {e}", exc_info=True)
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1
