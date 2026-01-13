"""Run shell script string tool.

This tool executes shell scripts directly without shell escaping issues.
It uses the SHELL_SCRIPT_#N placeholder system for script content.
"""

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class RunShellScriptStringTool(BaseTool):
    """
    Tool for executing shell script strings without shell escaping issues.

    **Use this tool instead of `run` with `bash -c "..."` for complex shell scripts.**

    **Benefits:**
    - No shell escaping issues (quotes, variables, etc.)
    - Better error messages (can show script content)
    - Cleaner code (no need to escape quotes)
    - Supports multi-line scripts easily

    **Usage:**
    Use SHELL_SCRIPT_#N placeholder in JSON, then provide script content:
    {
        "tool": "run_shell_script_string",
        "args": {
            "script": "SHELL_SCRIPT_#1"
        }
    }
    ---(SHELL_SCRIPT_#1)---
    #!/bin/bash
    set -e

    echo "Processing files..."
    for file in *.txt; do
        if [ -f "$file" ]; then
            echo "Found: $file"
            wc -l "$file"
        fi
    done
    ---

    **Important notes:**
    - Script runs in /workspace directory
    - Success is determined by stderr content, NOT exit code
    - Script is written to a temporary file, executed, then cleaned up
    - Uses bash to execute the script
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize run shell script string tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        """Tool name."""
        return "run_shell_script_string"

    @property
    def description(self) -> str:
        """Tool description."""
        return "执行shell脚本字符串（避免shell转义问题）"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "script" not in args:
            return False, "Missing required argument: 'script'"
        if not isinstance(args["script"], str):
            return False, "Argument 'script' must be a string"
        if not args["script"].strip():
            return False, "Argument 'script' cannot be empty"
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute shell script string.

        **Args:**
            args: Tool arguments dictionary
                - script (str, required): Shell script to execute. Can be multi-line.
                  Should use SHELL_SCRIPT_#N placeholder in JSON, actual content provided separately.
                - timeout_sec (int, optional): Timeout in seconds. Default: 600 (10 minutes).

        **Returns:**
            ToolResult with:
            - ok (bool): True if script succeeded (no errors in stderr)
            - stdout (str): Standard output from the script
            - stderr (str): Standard error from the script (empty string means success)
            - meta (dict): Contains script_preview, duration_ms

        **Examples:**
            # Simple script
            run_shell_script_string(script="SHELL_SCRIPT_#1")
            ---(SHELL_SCRIPT_#1)---
            echo "Hello, World!"
            ls -la
            ---

            # Complex script with loops and conditionals
            run_shell_script_string(script="SHELL_SCRIPT_#1")
            ---(SHELL_SCRIPT_#1)---
            #!/bin/bash
            set -e

            for file in *.py; do
                if [ -f "$file" ]; then
                    echo "Processing $file"
                    python3 -m py_compile "$file"
                fi
            done
            ---

        **⚠️ Critical: Success Determination**
        - **DO NOT rely on exit_code** - it's unreliable!
        - **Success = empty stderr** (no error messages)
        - **Failure = non-empty stderr** (contains error messages)
        - Always read stdout and stderr content to judge success
        """
        script = args["script"]
        timeout_sec = args.get("timeout_sec", 600)

        # Create temporary shell script file
        # Use /workspace/.atloop_temp for temp files (will be cleaned up)
        temp_dir = Path("/workspace") / ".atloop_temp"
        temp_dir.mkdir(exist_ok=True)

        # Create temp file with .sh extension
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", dir=str(temp_dir), delete=False
        ) as f:
            temp_file = Path(f.name)
            # Write script with shebang if not present
            if not script.strip().startswith("#!"):
                f.write("#!/bin/bash\n")
            f.write(script)
            # Make executable
            temp_file.chmod(0o755)

        try:
            # Execute shell script
            # Use bash explicitly, run from /workspace
            cmd = f"cd /workspace && bash {temp_file}"
            result = self.sandbox.exec_shell(
                command=cmd,
                workdir="/workspace",
                timeout_seconds=timeout_sec,
            )

            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            # Determine success based on stderr content, not exit code
            ok = not bool(stderr.strip())  # Success if no error messages in stderr

            # Create script preview for meta (first 200 chars)
            script_preview = script[:200] + "..." if len(script) > 200 else script

            return ToolResult(
                ok=ok,
                stdout=stdout,
                stderr=stderr,
                meta={
                    "script_preview": script_preview,
                    "script_length": len(script),
                    "duration_ms": result.get("durationMs", 0),
                },
            )
        finally:
            # Clean up temp file
            try:
                temp_file.unlink()
            except Exception as e:
                # Log but don't fail if cleanup fails
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"[RunShellScriptStringTool] Failed to cleanup temp file {temp_file}: {e}"
                )
