"""Exec-file command - execute task with prompt file."""

import logging
import sys
from pathlib import Path
from typing import Any

from atloop.api.runner import TaskRunner

logger = logging.getLogger(__name__)


def cmd_exec_file(args: Any) -> int:
    """Execute task with prompt file."""
    logger.debug(f"[CLI] Exec-file command called with args: {vars(args)}")

    try:
        # Read prompt from file
        prompt_file = Path(args.file_path)
        if not prompt_file.exists():
            print(f"Error: File not found: {prompt_file}", file=sys.stderr)
            return 1
        prompt = prompt_file.read_text(encoding="utf-8").strip()
        logger.debug(f"[CLI] Loaded prompt from file: {prompt_file} (length: {len(prompt)})")

        if not prompt:
            print(f"Error: Prompt file is empty: {prompt_file}", file=sys.stderr)
            return 1

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

        # Execute
        runner = TaskRunner(atloop_dir=getattr(args, "atloop_dir", None))
        logger.debug("[CLI] Starting task execution")
        result = runner.execute(goal=prompt, workspace_root=workspace_root, upload_workspace=upload_workspace)
        logger.debug(f"[CLI] Task execution completed: success={result['success']}")

        return 0 if result["success"] else 1
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error(f"[CLI] Exec-file command failed: {e}")
        logger.debug(f"[CLI] Exception details: {type(e).__name__}: {e}", exc_info=True)
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1
