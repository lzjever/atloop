"""Execute command - single task execution method."""

import logging
import sys
from pathlib import Path
from typing import Any

from atloop.api.runner import TaskRunner

logger = logging.getLogger(__name__)


def cmd_execute(args: Any) -> int:
    """Execute task - single method."""
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

        # Build config
        task_config = {
            "goal": prompt,
            "workspace_root": args.workspace,
            "sandbox": {
                "base_url": None if args.local_test else args.sandbox_url,
                "local_test": args.local_test,
            },
        }
        if args.session:
            task_config["session_id"] = args.session

        logger.debug(f"[CLI] Task config: {task_config}")

        # Execute
        runner = TaskRunner(atloop_dir=getattr(args, "atloop_dir", None))
        logger.debug("[CLI] Starting task execution")
        result = runner.execute(task_config, console=True)
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
