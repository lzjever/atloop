"""Run command tool."""

from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult
from atloop.tools.output_semantic_type import OutputSemanticType


class RunCommandTool(BaseTool):
    """
    Tool for executing shell commands in the sandbox workspace.

    **⚠️ This is the primary tool for executing system commands!**

    **Use cases:**
    - Running build commands (make, npm, pip, etc.)
    - Running tests (pytest, unittest, etc.)
    - Executing scripts (python3, node, etc.)
    - File operations (ls, cat, grep, find, etc.)
    - System checks (which, type, etc.)

    **Important notes:**
    - Commands run in /workspace directory
    - Success is determined by stderr content, NOT exit code
    - Many commands return exit_code=0 even with errors
    - Always check stdout and stderr content to judge success
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize run command tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        """Tool name."""
        return "run"

    @property
    def description(self) -> str:
        """Tool description."""
        return "执行shell命令（优先使用此工具执行系统命令）"

    @property
    def output_semantic_type(self) -> OutputSemanticType:
        """Return semantic type: EXECUTION_RESULT.

        Note: File view commands are handled specially in OutputLimitStrategy
        based on command content, not semantic type.
        """
        return OutputSemanticType.EXECUTION_RESULT

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "cmd" not in args:
            return False, "Missing required argument: 'cmd'"
        if not isinstance(args["cmd"], str):
            return False, "Argument 'cmd' must be a string"
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute shell command in the sandbox workspace.

        **⚠️ IMPORTANT**: This is the primary tool for executing system commands!
        Use this instead of trying to execute commands through other means.

        **Args:**
            args: Tool arguments dictionary
                - cmd (str, required): Shell command to execute. Can be any valid shell command.
                  Examples: "ls -la", "python3 script.py", "grep -rn 'pattern' .", etc.
                - timeout_sec (int, optional): Timeout in seconds. Default: 600 (10 minutes).
                  Use shorter timeouts for quick commands, longer for builds/tests.

        **Returns:**
            ToolResult with:
            - ok (bool): True if command succeeded (no errors in stderr)
            - stdout (str): Standard output from the command
            - stderr (str): Standard error from the command (empty string means success)
            - meta (dict): Contains cmd, duration_ms

        **Examples:**
            # List files
            run(cmd="ls -la")

            # Run Python script
            run(cmd="python3 script.py")

            # Run tests
            run(cmd="pytest tests/")

            # Search for pattern
            run(cmd="grep -rn 'def function' .")

            # View file content
            run(cmd="cat file.py")
            run(cmd="head -n 50 file.py")
            run(cmd="tail -n 20 file.py")

        **⚠️ Critical: Success Determination**
        - **DO NOT rely on exit_code** - it's unreliable!
        - **Success = empty stderr** (no error messages)
        - **Failure = non-empty stderr** (contains error messages)
        - Many commands return exit_code=0 even with errors (e.g., pytest collection errors)
        - Always read stdout and stderr content to judge success


        **⚠️ Hard requirement: avoid “triple-layer quoting hell”**
        If use python3 -c "....", you must use single quotes inside the string following "-c".
        Example:
        {
            "tool": "run",
            "args": {
                "cmd": "python3 -c \\"import sys; sys.path.insert(0, '.'); from jira_client import JiraClient; client = JiraClient(); projects = client.get_projects(); print('Projects:'); for p in projects: print(f\\"  {p['key']}: {p['name']}\\")\\""
            }
        }


        **Common Commands:**
        - File viewing: `cat`, `head`, `tail`, `less`, `more`
        - File search: `grep`, `find`, `locate`
        - Text processing: `sed`, `awk`, `cut`, `sort`, `uniq`
        - File operations: `ls`, `pwd`, `cd`, `mkdir`, `rm`, `cp`, `mv`
        - Python: `python3` (not `python`), `pip3` (not `pip`)
        - Other: `echo`, `wc`, `diff`, `which`, `type`

        **Error Handling:**
        - Success is determined by stderr content, not exit code
        - If stderr is empty, the command succeeded
        - If stderr contains "error", "failed", "exception", etc., command likely failed
        - Always check stderr content, not just ok field

        **⚠️ IMPORTANT: For Complex Python/Shell Scripts, Use Specialized Tools**

        DO NOT use `run` with `python3 -c "..."` or `bash -c "..."` for complex scripts!
        This causes shell escaping issues (quotes, f-strings, etc.).

        Instead, use:
        - `run_python_script_string` for Python code execution (use PYTHON_SCRIPT_#N placeholder)
        - `run_shell_script_string` for complex shell scripts (use SHELL_SCRIPT_#N placeholder)

        Use `run` only for simple commands: ls, cat, grep, find, pwd, python3 script.py, etc.
        """
        cmd = args["cmd"]
        timeout_sec = args.get("timeout_sec", 600)

        result = self.sandbox.exec_shell(
            command=cmd,
            workdir="/workspace",
            timeout_seconds=timeout_sec,
        )

        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        exit_code = result.get("exitCode", result.get("exit_code", -1))
        # Determine success based on stderr content, not exit code
        # Many commands return exit_code=0 even with errors, or exit_code!=0 with no errors
        ok = not bool(stderr.strip())  # Success if no error messages in stderr

        return ToolResult(
            ok=ok,
            stdout=stdout,
            stderr=stderr,
            meta={
                "cmd": cmd,
                "duration_ms": result.get("durationMs", 0),
                "exitCode": exit_code,  # Include exit code for proper display
            },
        )
