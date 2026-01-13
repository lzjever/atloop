"""atloop CLI - minimal implementation (uses varlord for CLI argument parsing)."""

import argparse
import sys

# CLI uses varlord for CLI argument parsing
from atloop.cli.commands import cmd_config, cmd_execute, cmd_init
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
            "  # Set log level via environment variable\n"
            "  ATLOOP_LOG_LEVEL=DEBUG atloopc execute --workspace ./workspace --prompt 'task'\n"
            "\n"
            "  # Use default INFO level\n"
            "  atloopc execute --workspace ./workspace --prompt 'task'\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    init_parser = subparsers.add_parser("init", help="Initialize configuration")
    add_atloop_dir_arg(init_parser)

    # execute (only execution method)
    execute_parser = subparsers.add_parser("execute", help="Execute a task")
    add_atloop_dir_arg(execute_parser)
    execute_parser.add_argument(
        "--workspace", help="Workspace directory (default: current directory)"
    )
    execute_parser.add_argument("--prompt", help="Task prompt (text)")
    execute_parser.add_argument("--prompt-file", help="Task prompt (file)")
    execute_parser.add_argument(
        "--sandbox-url", default="http://127.0.0.1:8080", help="Sandbox base URL"
    )
    execute_parser.add_argument("--local-test", action="store_true", help="Use local test mode")
    execute_parser.add_argument(
        "--sandbox-session", help="Sandbox session ID (overrides config default)"
    )
    execute_parser.add_argument(
        "--agent-session", help="Agent session ID for resuming/continuing runs"
    )
    execute_parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload workspace files to sandbox before execution (default: false)",
    )

    execute_parser.add_argument(
        "--help-variables", action="store_true", help="Show available variables and their sources"
    )

    execute_parser.add_argument(
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

    # Handle variable help and check commands (only for execute command)
    if hasattr(args, "help_variables") and args.help_variables:
        # Generate custom help text showing all configuration variables
        from varlord.metadata import get_all_fields_info

        field_infos = get_all_fields_info(config_obj._model)

        print("atloop Configuration Variables")
        print("=" * 80)
        print("\nAll configuration variables can be set via:")
        print("  1. YAML files: ~/.atloop/config/atloop.yaml or ./.atloop/config/atloop.yaml")
        print("  2. Environment variables: ATLOOP__<VARIABLE_NAME>")
        print("  3. .env file: ATLOOP__<VARIABLE_NAME>=value")
        print("\nVariable Mapping Rules:")
        print("  - Use double underscore (__) for nested keys")
        print("  - Example: ATLOOP__AI__COMPLETION__MODEL=deepseek-chat")
        print("  - Example: ATLOOP__RUNTIME__STUCK_SIGNATURE_REPEATS=3")
        print("\nAvailable Variables:")
        print("-" * 80)

        for field_info in field_infos:
            var_name = field_info.normalized_key
            var_type = (
                field_info.type.__name__
                if hasattr(field_info.type, "__name__")
                else str(field_info.type)
            )
            is_required = field_info.required
            description = field_info.description or "No description"

            # Handle default value display
            if is_required:
                default_str = ""
            elif field_info.default != "MISSING" and field_info.default is not None:
                # Show default value if available
                default_str = f" (default: {field_info.default})"
            elif field_info.default_factory != "MISSING":
                # Show default factory info
                default_str = " (has default factory)"
            else:
                default_str = ""

            env_var_name = f"ATLOOP__{var_name.upper().replace('.', '__')}"

            status = "Required" if is_required else f"Optional{default_str}"
            print(f"\n{var_name}")
            print(f"  Type: {var_type}")
            print(f"  Status: {status}")
            print(f"  Description: {description}")
            print(f"  Environment Variable: {env_var_name}")

        print("\n" + "=" * 80)
        print("For detailed variable diagnostics, use: atloop execute --check-variables")
        return 0

    if hasattr(args, "check_variables") and args.check_variables:
        diagnostic_table = config_obj.format_diagnostic_table()
        print(diagnostic_table)
        # Check if there are any missing required fields
        try:
            config_obj.load()
            print("\n✓ All required configuration variables are present")
            return 0
        except Exception as e:
            print(f"\n✗ Configuration validation failed: {e}", file=sys.stderr)
            return 1

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
