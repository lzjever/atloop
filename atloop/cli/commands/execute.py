"""Execute command - single task execution method."""

import logging
import sys
from pathlib import Path
from typing import Any

from atloop.api.runner import TaskRunner

logger = logging.getLogger(__name__)


def cmd_execute(args: Any) -> int:
    """Execute task - single method."""
    # Logging is already configured in main() via setup_logging()
    # which reads from ATLOOP_LOG_LEVEL environment variable
    logger.debug(f"[CLI] Execute command called with args: {vars(args)}")

    try:
        # Read prompt
        if args.prompt:
            prompt = args.prompt
            logger.debug(f"[CLI] Using prompt from command line (length: {len(prompt)})")
        elif args.prompt_file:
            prompt_file = Path(args.prompt_file)
            if not prompt_file.exists():
                print(f"Error: File not found: {prompt_file}", file=sys.stderr)
                return 1
            prompt = prompt_file.read_text(encoding="utf-8").strip()
            logger.debug(f"[CLI] Loaded prompt from file: {prompt_file} (length: {len(prompt)})")
        else:
            print("Error: --prompt or --prompt-file required", file=sys.stderr)
            return 1

        # Use current directory if workspace not specified
        if args.workspace:
            workspace = Path(args.workspace)
        else:
            workspace = Path.cwd()
            logger.debug(f"[CLI] No workspace specified, using current directory: {workspace}")
        
        # Create workspace if it doesn't exist
        if not workspace.exists():
            workspace.mkdir(parents=True, exist_ok=True)
            logger.debug(f"[CLI] Created workspace: {workspace}")
        

        # Build config
        task_config = {
            "goal": prompt,
            "workspace_root": str(workspace),
            "sandbox": {
                "base_url": None if args.local_test else args.sandbox_url,
                "local_test": args.local_test,
            },
        }
        if args.sandbox_session:
            task_config["sandbox_session_id"] = args.sandbox_session
        if args.agent_session:
            task_config["agent_session_id"] = args.agent_session

        logger.debug(f"[CLI] Task config: {task_config}")

        # Extract upload_workspace flag
        upload_workspace = getattr(args, "upload", False)

        # Execute
        runner = TaskRunner(atloop_dir=getattr(args, "atloop_dir", None))
        logger.debug("[CLI] Starting task execution")
        result = runner.execute(task_config, console=True, upload_workspace=upload_workspace)
        logger.debug(f"[CLI] Task execution completed: success={result['success']}")

        return 0 if result["success"] else 1
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error(f"[CLI] Execute command failed: {e}")
        logger.debug(f"[CLI] Exception details: {type(e).__name__}: {e}", exc_info=True)
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1
