"""atloop CLI - minimal implementation (uses varlord for CLI argument parsing)."""

import argparse
import sys

# CLI uses varlord for CLI argument parsing
from atloop.cli.commands import cmd_config, cmd_exec, cmd_exec_file, cmd_init
from atloop.cli.commands.variables import check_variables, show_variable_help
from atloop.cli.logging_config import setup_logging
from atloop.config.loader import ConfigLoader


def create_parser() -> argparse.ArgumentParser:
    """Create parser - single method."""
    parser = argparse.ArgumentParser(
        description="atloop - Task Automation Node",
        epilog=(
            "Environment Variables:\n"
            "  ATLOOP_LOG_LEVEL    Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).\n"
            "                       Default: INFO\n"
            "\n"
            "Examples:\n"
            "  # Execute with prompt string\n"
            "  atloopc exec 'fix the bug in main.py'\n"
            "\n"
            "  # Execute with prompt file\n"
            "  atloopc exec-file ./prompt.txt\n"
            "\n"
            "  # Configuration via varlord (YAML, env vars, or CLI args)\n"
            "  atloopc exec 'task' --sandbox-base-url http://localhost:8080\n"
            "  ATLOOP__RUNTIME__UPLOAD_WORKSPACE=true atloopc exec 'task'\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize configuration")
    add_atloop_dir_arg(init_parser)

    # exec - execute with prompt string
    exec_parser = subparsers.add_parser("exec", help="Execute a task with prompt string")
    add_atloop_dir_arg(exec_parser)
    exec_parser.add_argument(
        "prompt", nargs="?", help="Task prompt (text). If not provided, reads from stdin."
    )
    exec_parser.add_argument(
        "--output-format",
        choices=["minimal", "verbose", "debug"],
        default="minimal",
        help="Output format: minimal (default), verbose, or debug",
    )
    exec_parser.add_argument(
        "--help-variables", action="store_true", help="Show available variables and their sources"
    )
    exec_parser.add_argument(
        "--check-variables", action="store_true", help="Check variables and exit"
    )

    # exec-file - execute with prompt file
    exec_file_parser = subparsers.add_parser("exec-file", help="Execute a task with prompt file")
    add_atloop_dir_arg(exec_file_parser)
    exec_file_parser.add_argument("file_path", help="Path to prompt file")
    exec_file_parser.add_argument(
        "--output-format",
        choices=["minimal", "verbose", "debug"],
        default="minimal",
        help="Output format: minimal (default), verbose, or debug",
    )
    exec_file_parser.add_argument(
        "--help-variables", action="store_true", help="Show available variables and their sources"
    )
    exec_file_parser.add_argument(
        "--check-variables", action="store_true", help="Check variables and exit"
    )

    # config
    config_parser = subparsers.add_parser("config", help="Show configuration")
    add_atloop_dir_arg(config_parser)

    return parser


def add_atloop_dir_arg(parser: argparse.ArgumentParser) -> None:
    """Add atloop-dir argument."""
    parser.add_argument("--atloop-dir", help="Custom config directory")


def main() -> int:
    """Main entry point."""
    # Setup logging from environment variable before parsing arguments
    # This ensures logging is configured early for all commands
    setup_logging()

    parser = create_parser()
    args, unknown_args = parser.parse_known_args()

    # Initialize ConfigLoader early so it's available everywhere
    # Extract atloop_dir from args (available in all subcommands via add_atloop_dir_arg)
    atloop_dir = getattr(args, "atloop_dir", None)
    config_obj = ConfigLoader.setup(atloop_dir=atloop_dir)

    # Handle variable help and check commands (for exec and exec-file commands)
    if hasattr(args, "help_variables") and args.help_variables:
        return show_variable_help(config_obj)

    if hasattr(args, "check_variables") and args.check_variables:
        return check_variables(config_obj)

    try:
        if args.command == "init":
            return cmd_init(args)
        elif args.command == "exec":
            return cmd_exec(args)
        elif args.command == "exec-file":
            return cmd_exec_file(args)
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
