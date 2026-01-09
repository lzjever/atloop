"""atloop CLI - minimal implementation (uses varlord for CLI argument parsing)."""

import argparse
import sys

# CLI uses varlord for CLI argument parsing
from atloop.cli.commands import cmd_config, cmd_execute, cmd_init


def create_parser() -> argparse.ArgumentParser:
    """Create parser - single method."""
    parser = argparse.ArgumentParser(description="atloop - Task Automation Node")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize configuration")
    add_atloop_dir_arg(init_parser)

    # execute (only execution method)
    execute_parser = subparsers.add_parser("execute", help="Execute a task")
    add_atloop_dir_arg(execute_parser)
    execute_parser.add_argument("--workspace", required=True, help="Workspace directory")
    execute_parser.add_argument("--prompt", help="Task prompt (text)")
    execute_parser.add_argument("--prompt-file", help="Task prompt (file)")
    execute_parser.add_argument(
        "--sandbox-url", default="http://127.0.0.1:8080", help="Sandbox base URL"
    )
    execute_parser.add_argument("--local-test", action="store_true", help="Use local test mode")
    execute_parser.add_argument("--session", help="Session ID")

    # config
    config_parser = subparsers.add_parser("config", help="Show configuration")
    add_atloop_dir_arg(config_parser)

    return parser


def add_atloop_dir_arg(parser: argparse.ArgumentParser) -> None:
    """Add atloop-dir argument."""
    parser.add_argument("--atloop-dir", help="Custom config directory")


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        if args.command == "init":
            return cmd_init(args)
        elif args.command == "execute":
            return cmd_execute(args)
        elif args.command == "config":
            return cmd_config(args)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
