"""Edit file tool with Git-style diff editing."""

import shlex
from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class EditFileTool(BaseTool):
    """
    Tool for editing files using Git-style diff (old_string -> new_string).

    **⚠️ This is the preferred tool for modifying existing files!**

    **Why use edit_file instead of write_file:**
    - ✅ More precise: Only modifies the specified part
    - ✅ Safer: Doesn't risk overwriting unrelated code
    - ✅ More efficient: No need to read and rewrite entire file
    - ✅ Better for local modifications: Functions, classes, paragraphs, etc.

    **Safety features:**
    - Match count validation: Only replaces if old_string appears exactly once
    - Prevents accidental multiple replacements
    - Clear error messages when matches are not found or ambiguous

    **Use cases:**
    - Modifying a function or method
    - Updating a class definition
    - Changing a specific section of code
    - Fixing a bug in a specific location
    - Updating configuration values
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize edit file tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        """Tool name."""
        return "edit_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "编辑文件（Git 风格 diff 编辑，使用 content 参数，格式为 <old>old_string</old><new>new_string</new>）"

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

        # Parse content to extract old_string and new_string
        content = args["content"]
        import re

        old_match = re.search(r"<old>(.*?)</old>", content, re.DOTALL)
        new_match = re.search(r"<new>(.*?)</new>", content, re.DOTALL)

        if not old_match or not new_match:
            return False, "content must be in format: <old>old_string</old><new>new_string</new>"

        old_string = old_match.group(1)
        new_string = new_match.group(1)

        # Check if old_string and new_string are the same
        if old_string == new_string:
            return False, "old_string and new_string are the same. No changes to make."

        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute edit file tool.

        **⚠️ IMPORTANT**: This is the preferred tool for modifying existing files!
        Use this instead of `write_file` for any file modifications.

        **Args:**
            args: Tool arguments dictionary
                - path (str, required): File path. Relative paths are relative to /workspace.
                - content (str, required): Content in format `<old>old_string</old><new>new_string</new>`.
                  The old_string is the exact text to replace. Must match exactly including
                  whitespace, indentation, and newlines. Should include at least 3 lines of context
                  before and after to ensure uniqueness.
                - replace_all (bool, optional): If True, replace all occurrences of old_string.
                  Default: False. When False, only replaces if old_string appears exactly once.

        **Returns:**
            ToolResult with:
            - ok (bool): True if edit was successful (no errors in stderr)
            - stdout (str): Diff summary (e.g., "Updated file: +2 lines, -1 lines")
            - stderr (str): Error messages if any (empty string means success)
            - meta (dict): Contains path, operation, replace_all

        **Examples:**
            # Modify a function
            edit_file(
                path="src/utils.py",
                content="<old>def calculate(x, y):\n    return x + y</old><new>def calculate(x, y):\n    return x * y</new>"
            )

            # Add context for uniqueness
            edit_file(
                path="src/main.py",
                content="<old># Configuration\nDEBUG = True\n# End config</old><new># Configuration\nDEBUG = False\n# End config</new>"
            )

        **Safety Checks:**
        - **Match count validation**: When replace_all=False (default):
          - If old_string appears 0 times → Error: "old_string not found"
          - If old_string appears 1 time → Success: Replaces it
          - If old_string appears 2+ times → Error: "found X times, make old_string more specific"
        - **When replace_all=True**: Replaces all occurrences without validation

        **Best Practices:**
        1. **Include context**: Add at least 3 lines before and after the code you're changing
        2. **Be precise**: Match exact whitespace, indentation, and newlines
        3. **Make it unique**: Ensure old_string appears only once in the file
        4. **Use read_file first**: Read the file to see exact formatting before editing

        **Error Messages:**
        - "old_string not found" → Check that old_string exactly matches file content
        - "found X times" → Add more context to make old_string unique, or use replace_all=True
        - "File not found" → File doesn't exist

        **Note on Trailing Newlines:**
        Files always end with exactly one newline character after editing, regardless of
        whether new_string ends with a newline or not.
        """
        path = args["path"]
        content = args["content"]
        replace_all = args.get("replace_all", False)

        # Parse content to extract old_string and new_string
        import re

        old_match = re.search(r"<old>(.*?)</old>", content, re.DOTALL)
        new_match = re.search(r"<new>(.*?)</new>", content, re.DOTALL)

        if not old_match or not new_match:
            return ToolResult(
                ok=False,
                stdout="",
                stderr="Invalid content format. Expected format: <old>old_string</old><new>new_string</new>",
                meta={"path": path},
            )

        old_string = old_match.group(1)
        new_string = new_match.group(1)

        # Handle paths - sandbox runs in /workspace directory
        # Relative paths are already relative to /workspace
        path_escaped = shlex.quote(path)

        # Check if file exists
        if old_string:
            check_cmd = f"test -f {path_escaped} && echo 'exists' || echo 'not_found'"
            check_result = self._run_command(check_cmd, timeout_sec=5)

            if "not_found" in check_result["stdout"]:
                return ToolResult(
                    ok=False,
                    stdout="",
                    stderr=f"File not found: {path}. Cannot edit non-existent file.",
                    meta={"path": path, "file_type": "not_found"},
                )

            # Read current file content
            read_cmd = f"cat {path_escaped} 2>/dev/null"
            read_result = self._run_command(read_cmd, timeout_sec=30)

            # Check for read errors in stderr, not exit code
            if read_result.get("stderr", "").strip():
                return ToolResult(
                    ok=False,
                    stdout="",
                    stderr=f"Failed to read file: {path}. Error: {read_result.get('stderr', 'Unknown error')}",
                    meta={"path": path},
                )

            original_content = read_result.get("stdout", "")

            # Normalize line endings (handle both LF and CRLF)
            original_content = self._normalize_line_endings(original_content)
            old_string_normalized = self._normalize_line_endings(old_string)
            new_string_normalized = self._normalize_line_endings(new_string)

            # Handle edge case: if new_string is empty and old_string doesn't end with newline,
            # but the file has old_string + newline, match that
            old_string_for_replace = old_string_normalized
            if new_string_normalized == "" and not old_string_normalized.endswith("\n"):
                if original_content.find(old_string_normalized + "\n") != -1:
                    old_string_for_replace = old_string_normalized + "\n"

            # Count occurrences for safety check
            match_count = original_content.count(old_string_for_replace)

            # Safety check: only replace if exactly one match (unless replace_all is True)
            if replace_all:
                # Replace all occurrences
                updated_content = original_content.replace(
                    old_string_for_replace, new_string_normalized
                )
            else:
                # Only replace if exactly one match
                if match_count == 0:
                    return ToolResult(
                        ok=False,
                        stdout="",
                        stderr="Edit failed: old_string not found in file. The text you're trying to replace does not exist in the file. Please check the old_string and try again.",
                        meta={"path": path, "match_count": 0},
                    )
                elif match_count > 1:
                    return ToolResult(
                        ok=False,
                        stdout="",
                        stderr=f"Edit failed: old_string found {match_count} times in file. To ensure safety, edit_file only replaces when old_string appears exactly once. Please make old_string more specific (add more context) to uniquely identify the location, or use replace_all=true to replace all occurrences.",
                        meta={"path": path, "match_count": match_count},
                    )
                else:
                    # Exactly one match - safe to replace
                    updated_content = original_content.replace(
                        old_string_for_replace, new_string_normalized, 1
                    )

            # Check if content actually changed (shouldn't happen with our checks, but just in case)
            if updated_content == original_content:
                return ToolResult(
                    ok=False,
                    stdout="",
                    stderr="Edit failed: No changes made. This should not happen - please report this error.",
                    meta={"path": path},
                )

        # Write updated content
        # Heredoc automatically adds a newline before FILE_EOF, so we need to handle trailing newlines
        # If content ends with \n, remove it to avoid double newline
        content_for_write = updated_content
        if content_for_write.endswith("\n"):
            content_for_write = content_for_write[:-1]

        write_cmd = f"cat > {path_escaped} <<'FILE_EOF'\n{content_for_write}\nFILE_EOF"
        write_result = self._run_command(write_cmd, timeout_sec=30)

        # Check for write errors in stderr, not exit code
        if write_result.get("stderr", "").strip():
            return ToolResult(
                ok=False,
                stdout="",
                stderr=f"Failed to write file: {path}. Error: {write_result.get('stderr', 'Unknown error')}",
                meta={"path": path},
            )

        # Generate diff summary
        diff_summary = self._generate_diff_summary(
            original_content,
            updated_content,
            old_string,
            new_string,
        )

        return ToolResult(
            ok=True,
            stdout=diff_summary,
            stderr="",
            meta={
                "path": path,
                "operation": "create"
                if not old_string
                else ("delete" if not new_string else "update"),
                "replace_all": replace_all,
            },
        )

    def _normalize_line_endings(self, text: str) -> str:
        """Normalize line endings to LF."""
        # Replace CRLF with LF, then ensure all are LF
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def _generate_diff_summary(
        self,
        original: str,
        updated: str,
        old_string: str,
        new_string: str,
    ) -> str:
        """Generate a human-readable diff summary."""
        if not new_string:
            # Deletion
            return f"Removed {len(old_string.split(chr(10)))} lines."

        # Calculate line changes
        old_lines = old_string.split("\n")
        new_lines = new_string.split("\n")

        # Simple diff: count added/removed lines
        # This is a simplified version - full diff would use diff algorithm
        if len(new_lines) > len(old_lines):
            added = len(new_lines) - len(old_lines)
            return f"Updated file: +{added} lines, -{len(old_lines)} lines, +{len(new_lines)} lines total."
        elif len(new_lines) < len(old_lines):
            removed = len(old_lines) - len(new_lines)
            return f"Updated file: -{removed} lines, +{len(new_lines)} lines, -{len(old_lines)} lines total."
        else:
            return f"Updated file: {len(old_lines)} lines modified."

    def _run_command(self, cmd: str, timeout_sec: int = 600) -> Dict[str, Any]:
        """Run a shell command in sandbox."""
        return self.sandbox.exec_shell(
            command=cmd,
            workdir="/workspace",
            timeout_seconds=timeout_sec,
        )
