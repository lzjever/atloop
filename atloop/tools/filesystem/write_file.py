"""Write file tool."""

import shlex
from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class WriteFileTool(BaseTool):
    """
    Tool for writing files (creates new files or completely overwrites existing files).

    **⚠️ Important Usage Guidelines:**
    - **Use for**: Creating new files or completely rewriting existing files
    - **Do NOT use for**: Modifying parts of existing files (use `edit_file` instead)
    - **Character limit**: Maximum 6,000 characters per turn
    - **Directory creation**: Automatically creates parent directories if they don't exist

    **When to use write_file vs edit_file:**
    - ✅ Creating a new file → use `write_file`
    - ✅ Completely rewriting a file → use `write_file`
    - ❌ Modifying a function/class → use `edit_file` (more precise and safer)
    - ❌ Adding/removing a few lines → use `edit_file` (more precise and safer)

    **File content handling:**
    - Uses placeholder mechanism: content should be `FILE_CONTENT_#1`, `FILE_CONTENT_#2`, etc.
    - Actual content follows the JSON output, delimited by `---(FILE_CONTENT_#1)---`
    - This prevents JSON parsing issues with large content

    **Trailing newline behavior:**
    - Files always end with exactly one newline character
    - Input content's trailing newline is normalized automatically
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize write file tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        """Tool name."""
        return "write_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "写入文件（完全覆盖整个文件内容。如果要修改文件的部分内容，请使用 edit_file；如果要追加内容，请使用 append_file）"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "path" not in args:
            return False, "Missing required argument: 'path'"
        if "content" not in args:
            return False, "Missing required argument: 'content'"
        if not isinstance(args["path"], str):
            return False, "Argument 'path' must be a string"
        if not isinstance(args["content"], str):
            return False, "Argument 'content' must be a string"
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute write file tool.

        **⚠️ WARNING**: This tool completely overwrites the entire file. If the file exists,
        all existing content will be replaced with the new content.

        **When to use this tool:**
        - ✅ Creating a new file
        - ✅ Completely rewriting an existing file
        - ❌ Modifying part of a file → use `edit_file` instead
        - ❌ Appending content → use `append_file` instead

        **Args:**
            args: Tool arguments dictionary
                - path (str, required): File path. Relative paths are relative to /workspace.
                  Parent directories are automatically created if they don't exist.
                - content (str, required): File content to write. This will completely
                  replace any existing file content. Maximum 6,000 characters per turn.
                  Use placeholder `FILE_CONTENT_#1` in JSON, actual content follows after.

        **Returns:**
            ToolResult with:
            - ok (bool): True if file was written successfully (no errors in stderr)
            - stdout (str): Command output (usually empty)
            - stderr (str): Error messages if any (empty string means success)
            - meta (dict): Contains path, cmd, duration_ms

        **Examples:**
            # Create a new Python file
            write_file(path="src/main.py", content="FILE_CONTENT_#1")
            # Then provide actual content after JSON:
            # ---(FILE_CONTENT_#1)---
            # def main():
            #     print("Hello, World!")
            # ---(FILE_CONTENT_#1)---

        **Note on Trailing Newlines:**
        This tool uses heredoc (cat > file <<'FILE_EOF') which automatically adds a trailing
        newline. The tool normalizes input to ensure files always end with exactly one newline:
        - If content ends with '\\n', it's removed before writing (heredoc adds one)
        - If content doesn't end with '\\n', heredoc adds one
        - Result: File always ends with exactly one newline character
        - Exception: Empty string content results in a file with one newline

        **Error Handling:**
        - Success is determined by stderr content, not exit code
        - If stderr is empty, the operation succeeded
        - Check stderr for specific error messages if ok=False
        """
        path = args["path"]
        content = args["content"]

        # Handle paths - sandbox runs in /workspace directory
        # Relative paths are already relative to /workspace
        path_escaped = shlex.quote(path)

        # Ensure directory exists - create parent directories if needed
        import os

        dir_path = os.path.dirname(path)
        if dir_path:
            dir_path_escaped = shlex.quote(dir_path)
            mkdir_cmd = f"mkdir -p {dir_path_escaped}"
            mkdir_result = self.sandbox.exec_shell(
                command=mkdir_cmd,
                workdir="/workspace",
                timeout_seconds=10,
            )
            # Check if directory creation had errors in stderr
            if mkdir_result.get("stderr", "").strip():
                # Directory creation may have failed, but continue anyway
                # The write operation will fail if directory doesn't exist
                pass

        # Use heredoc to write file
        # Heredoc automatically adds a newline before FILE_EOF, so we need to handle trailing newlines
        # If content ends with \n, remove it to avoid double newline
        content_for_write = content
        if content_for_write.endswith("\n"):
            content_for_write = content_for_write[:-1]

        cmd = f"cat > {path_escaped} <<'FILE_EOF'\n{content_for_write}\nFILE_EOF"
        result = self.sandbox.exec_shell(
            command=cmd,
            workdir="/workspace",
            timeout_seconds=30,
        )

        # Determine success based on stderr content, not exit code
        stderr = result.get("stderr", "")
        ok = not bool(stderr.strip())  # Success if no error messages in stderr

        return ToolResult(
            ok=ok,
            stdout=result.get("stdout", ""),
            stderr=stderr,
            meta={"path": path, "cmd": cmd, "duration_ms": result.get("durationMs", 0)},
        )
