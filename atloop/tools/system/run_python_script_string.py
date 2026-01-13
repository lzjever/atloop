"""Run Python script string tool.

This tool executes Python code directly without shell escaping issues.
It uses the PYTHON_SCRIPT_#N placeholder system for script content.
"""

import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class RunPythonScriptStringTool(BaseTool):
    """
    Tool for executing Python code strings without shell escaping issues.

    **Use this tool instead of `run` with `python3 -c "..."` for complex Python code.**

    **Benefits:**
    - No shell escaping issues (quotes, f-strings, etc.)
    - Better error messages (can show script content)
    - Cleaner code (no need to escape quotes)

    **Usage:**
    Use PYTHON_SCRIPT_#N placeholder in JSON, then provide script content:
    {
        "tool": "run_python_script_string",
        "args": {
            "script": "PYTHON_SCRIPT_#1"
        }
    }
    ---(PYTHON_SCRIPT_#1)---
    import sys
    from jira_client import JiraClient

    client = JiraClient()
    projects = client.get_projects()
    for p in projects:
        print(f"{p['key']}: {p['name']}")
    ---

    **Important notes:**
    - Script runs in /workspace directory
    - Success is determined by stderr content, NOT exit code
    - Script is written to a temporary file, executed, then cleaned up
    - Python path includes /workspace automatically
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize run Python script string tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        """Tool name."""
        return "run_python_script_string"

    @property
    def description(self) -> str:
        """Tool description."""
        return "执行Python代码字符串（避免shell转义问题）"

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
        Execute Python script string.

        **Args:**
            args: Tool arguments dictionary
                - script (str, required): Python code to execute. Can be multi-line.
                  Should use PYTHON_SCRIPT_#N placeholder in JSON, actual content provided separately.
                - timeout_sec (int, optional): Timeout in seconds. Default: 600 (10 minutes).

        **Returns:**
            ToolResult with:
            - ok (bool): True if script succeeded (no errors in stderr)
            - stdout (str): Standard output from the script
            - stderr (str): Standard error from the script (empty string means success)
            - meta (dict): Contains script_preview, duration_ms

        **Examples:**
            # Simple script
            run_python_script_string(script="PYTHON_SCRIPT_#1")
            ---(PYTHON_SCRIPT_#1)---
            print("Hello, World!")
            ---

            # Complex script with imports
            run_python_script_string(script="PYTHON_SCRIPT_#1")
            ---(PYTHON_SCRIPT_#1)---
            import sys
            sys.path.insert(0, '.')
            from my_module import MyClass
            obj = MyClass()
            result = obj.process()
            print(f"Result: {result}")
            ---

        **⚠️ Critical: Success Determination**
        - **DO NOT rely on exit_code** - it's unreliable!
        - **Success = empty stderr** (no error messages)
        - **Failure = non-empty stderr** (contains error messages)
        - Always read stdout and stderr content to judge success
        """
        script = args["script"]
        timeout_sec = args.get("timeout_sec", 600)

        # Create temporary Python file
        # Use /workspace/.atloop_temp for temp files (will be cleaned up)
        temp_dir = Path("/workspace") / ".atloop_temp"
        temp_dir.mkdir(exist_ok=True)

        # Create temp file with .py extension
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", dir=str(temp_dir), delete=False
        ) as f:
            temp_file = Path(f.name)
            f.write(script)

        try:
            # Execute Python script
            # Use python3 explicitly, add /workspace to path
            cmd = f"cd /workspace && python3 {temp_file}"
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
                    f"[RunPythonScriptStringTool] Failed to cleanup temp file {temp_file}: {e}"
                )
