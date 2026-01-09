"""Append file tool."""

import shlex
from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class AppendFileTool(BaseTool):
    """
    Tool for appending content to the end of existing files.

    **⚠️ This tool is fully available and can be used normally!**

    **Use cases:**
    - Continuing to write files that exceed 6,000 characters (after initial write_file)
    - Adding log entries
    - Appending comments or notes
    - Building files incrementally

    **Key differences from write_file and edit_file:**
    - `write_file`: Completely overwrites file (creates or replaces entire file)
    - `edit_file`: Replaces specific text within file (precise modifications)
    - `append_file`: Adds content to end of file (doesn't modify existing content)

    **Content handling:**
    - Content is appended exactly as provided
    - Preserves trailing newlines in input content
    - Unlike write_file/edit_file, doesn't normalize trailing newlines
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize append file tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        """Tool name."""
        return "append_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "追加内容到文件（在现有文件末尾添加内容）"

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
        Execute append file tool.

        **⚠️ IMPORTANT**: This tool is fully available and can be used normally!
        Don't assume it's unavailable - it works perfectly fine.

        **Args:**
            args: Tool arguments dictionary
                - path (str, required): File path. Relative paths are relative to /workspace.
                  File must exist (this tool appends to existing files, doesn't create new ones).
                - content (str, required): Content to append to the end of the file.

        **Returns:**
            ToolResult with:
            - ok (bool): True if content was appended successfully (no errors in stderr)
            - stdout (str): Command output (usually empty)
            - stderr (str): Error messages if any (empty string means success)
            - meta (dict): Contains path, cmd, duration_ms

        **Examples:**
            # Continue writing a long document (after initial write_file with 6k chars)
            append_file(
                path="long_document.md",
                content="\\n\\n## Chapter 2\\nThis is the continuation..."
            )

            # Add a log entry
            append_file(
                path="app.log",
                content="[2024-01-01] User logged in\\n"
            )

        **Content Appending Behavior:**
        - Content is appended **exactly as provided**, without modification
        - If content ends with '\\n', it's appended with the newline
        - If content doesn't end with '\\n', it's appended without a newline
        - This differs from `write_file` and `edit_file`, which normalize trailing newlines
        - Use this when you need precise control over trailing newlines

        **Common Workflow:**
        1. First turn: Use `write_file` to create file with first 6k characters
        2. Subsequent turns: Use `append_file` to continue adding content
        3. Check file: Use `read_file` to verify complete content

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
        content_escaped = shlex.quote(content)

        # Use printf to append content exactly as provided (no extra newline)
        # printf '%s' ensures exact content without heredoc's trailing newline
        cmd = f"printf '%s' {content_escaped} >> {path_escaped}"
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
