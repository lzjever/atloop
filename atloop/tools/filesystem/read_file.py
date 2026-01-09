"""Read file tool with enhanced capabilities."""

import shlex
from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """
    Tool for reading files from the sandbox workspace with type detection and chunked reading.

    **Features:**
    - Automatic file type detection (text/binary)
    - Support for large files via line range reading
    - Binary file detection and handling
    - File size limits (10MB max for full read)

    **Use cases:**
    - Reading source code files
    - Reading configuration files
    - Reading documentation files
    - Reading log files (with line ranges)

    **Note**: This tool reads from the sandbox workspace (/workspace), not from the local machine.
    For reading skill files (stored locally), use `read_skill_file` instead.
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize read file tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        """Tool name."""
        return "read_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "读取文件内容（增强的文件读取工具，支持类型检测和大文件分块）"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "path" not in args:
            return False, "Missing required argument: 'path'"
        if not isinstance(args["path"], str):
            return False, "Argument 'path' must be a string"
        if "offset" in args and not isinstance(args.get("offset"), int):
            return False, "Argument 'offset' must be an integer"
        if "limit" in args and not isinstance(args.get("limit"), int):
            return False, "Argument 'limit' must be an integer"
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute read file tool.

        **Args:**
            args: Tool arguments dictionary
                - path (str, required): File path. Relative paths are relative to /workspace.
                  Absolute paths are used as-is.
                - offset (int, optional): Start line number (1-indexed). Default: 1 (start of file).
                  Use this for reading large files in chunks.
                - limit (int, optional): Number of lines to read. If not specified, reads from
                  offset to end of file. Use this for reading large files in chunks.

        **Returns:**
            ToolResult with:
            - ok (bool): True if file was read successfully (no errors in stderr)
            - stdout (str): File content (or metadata for binary/large files)
            - stderr (str): Error messages if any (empty string means success)
            - meta (dict): Contains path, file_type, file_size, start_line, end_line

        **Examples:**
            # Read entire file
            read_file(path="src/main.py")

            # Read first 100 lines
            read_file(path="src/main.py", offset=1, limit=100)

            # Read lines 50-100
            read_file(path="src/main.py", offset=50, limit=51)

            # Read from line 200 to end
            read_file(path="src/main.py", offset=200)

        **Behavior:**
        - **Text files**: Returns file content in stdout
        - **Binary files**: Returns metadata message (file type, size) instead of content
        - **Large files (>10MB)**: Returns metadata message, suggests using line ranges
        - **File not found**: Returns ok=False with error message in stderr
        - **Line ranges**: If offset/limit specified, only reads those lines

        **Path Handling:**
        - All commands run with workdir="/workspace"
        - Relative paths are resolved relative to /workspace
        - Absolute paths are used as-is

        **Error Handling:**
        - Success is determined by stderr content, not exit code
        - If stderr is empty, the operation succeeded
        - Check stderr for specific error messages if ok=False
        """
        path = args["path"]
        offset = args.get("offset")
        limit = args.get("limit")

        # Handle paths - sandbox runs in /workspace directory
        # Relative paths are already relative to /workspace (consistent with other tools)
        # Use relative path directly since workdir is /workspace
        path_escaped = shlex.quote(path)

        # Check if file exists (relative to /workspace)
        check_cmd = f"test -f {path_escaped} && echo 'exists' || echo 'not_found'"
        check_result = self._run_command(check_cmd, timeout_sec=5)

        if "not_found" in check_result["stdout"]:
            return ToolResult(
                ok=False,
                stdout="",
                stderr=f"File not found: {path}",
                meta={"path": path, "file_type": "not_found"},
            )

        # Detect file type
        detect_cmd = f"file -b {path_escaped} 2>/dev/null || echo 'unknown'"
        file_type_result = self._run_command(detect_cmd, timeout_sec=5)
        file_type_info = (
            file_type_result["stdout"].strip()
            if not file_type_result.get("stderr", "").strip()
            else "unknown"
        )

        # Check file size
        size_cmd = f"wc -c < {path_escaped} 2>/dev/null || echo '0'"
        size_result = self._run_command(size_cmd, timeout_sec=5)
        try:
            file_size = int(size_result["stdout"].strip())
        except (ValueError, AttributeError):
            file_size = 0

        # Check if binary
        is_binary = False
        if file_size > 0:
            check_binary_cmd = f"head -c 512 {path_escaped} 2>/dev/null | od -An -tx1 | grep -q ' 00 ' && echo 'binary' || echo 'text'"
            binary_check = self._run_command(check_binary_cmd, timeout_sec=5)
            if not binary_check.get("stderr", "").strip():
                is_binary = "binary" in binary_check["stdout"]
            else:
                is_binary = (
                    "text" not in file_type_info.lower() and "ascii" not in file_type_info.lower()
                )

        # If binary or too large, return metadata only
        max_file_size = 10 * 1024 * 1024  # 10MB
        is_text_file = (
            "text" in file_type_info.lower()
            or "ascii" in file_type_info.lower()
            or "python" in file_type_info.lower()
            or "script" in file_type_info.lower()
        )

        if (is_binary and not is_text_file) or file_size > max_file_size:
            return ToolResult(
                ok=True,
                stdout=f"[File: {path}]\nType: {file_type_info}\nSize: {file_size} bytes\n\nThis file is binary or too large to display. Use specific line ranges if needed.",
                stderr="",
                meta={
                    "path": path,
                    "file_type": "binary" if is_binary else "large",
                    "file_size": file_size,
                    "file_type_info": file_type_info,
                },
            )

        # Determine line range
        start_line = offset if offset is not None else 1
        if limit is not None:
            end_line = start_line + limit - 1 if start_line > 0 else limit
        else:
            end_line = None

        # Read file content
        if end_line is None:
            # Read from start_line to end of file
            if start_line == 1:
                cmd = f"cat {path_escaped} 2>/dev/null"
            else:
                # Use sed to read from start_line to end
                cmd = f"sed -n '{start_line},$p' {path_escaped} 2>/dev/null"
        else:
            cmd = f"sed -n '{start_line},{end_line}p' {path_escaped} 2>/dev/null || head -n {end_line} {path_escaped} | tail -n +{start_line}"

        result = self._run_command(cmd, timeout_sec=30)

        # Determine success based on stderr content, not exit code
        stderr = result.get("stderr", "")
        ok = not bool(stderr.strip())  # Success if no error messages in stderr

        return ToolResult(
            ok=ok,
            stdout=result.get("stdout", ""),
            stderr=stderr,
            meta={
                "path": path,
                "file_type": "text",
                "file_size": file_size,
                "file_type_info": file_type_info,
                "start_line": start_line,
                "end_line": end_line,
            },
        )

    def _run_command(self, cmd: str, timeout_sec: int = 600) -> Dict[str, Any]:
        """Run a shell command in sandbox."""
        return self.sandbox.exec_shell(
            command=cmd,
            workdir="/workspace",
            timeout_seconds=timeout_sec,
        )
