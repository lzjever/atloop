"""Variable help and diagnostics commands."""

import sys

from varlord.metadata import get_all_fields_info


def show_variable_help(config_obj) -> int:
    """Show all available configuration variables."""
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

        if is_required:
            default_str = ""
        elif field_info.default != "MISSING" and field_info.default is not None:
            default_str = f" (default: {field_info.default})"
        elif field_info.default_factory != "MISSING":
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


def check_variables(config_obj) -> int:
    """Check configuration variables."""
    diagnostic_table = config_obj.format_diagnostic_table()
    print(diagnostic_table)
    try:
        config_obj.load()
        print("\n✓ All required configuration variables are present")
        return 0
    except Exception as e:
        print(f"\n✗ Configuration validation failed: {e}", file=sys.stderr)
        return 1
