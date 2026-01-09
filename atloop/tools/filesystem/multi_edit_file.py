"""Multi-edit file tool for batch file editing."""

import shlex
from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class MultiEditFileTool(BaseTool):
    """
    Tool for editing multiple files in a single atomic transaction.

    **Key Features:**
    - **Transactional**: All edits succeed or all fail (atomicity)
    - **Batch operations**: Edit multiple files in one operation
    - **Rollback on error**: If any edit fails, all changes are rolled back

    **Use cases:**
    - Updating imports across multiple files
    - Refactoring code that spans multiple files
    - Applying the same change to multiple files
    - Coordinated updates that must happen together

    **When to use:**
    - ✅ Need to edit multiple files atomically
    - ✅ Changes must all succeed or all fail
    - ❌ Single file edit → use `edit_file` (simpler)
    - ❌ Independent edits → use multiple `edit_file` calls
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize multi-edit file tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        """Tool name."""
        return "multi_edit_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "批量编辑多个文件（事务性提交，支持多文件同时编辑）"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "edits" not in args:
            return False, "Missing required argument: 'edits'"
        if not isinstance(args["edits"], list):
            return False, "Argument 'edits' must be a list"
        if len(args["edits"]) == 0:
            return False, "Argument 'edits' must contain at least one edit"

        # Validate each edit
        for i, edit in enumerate(args["edits"]):
            if not isinstance(edit, dict):
                return False, f"Edit[{i}] must be a dictionary"
            if "path" not in edit:
                return False, f"Edit[{i}] missing required field: 'path'"
            if "old_string" not in edit:
                return False, f"Edit[{i}] missing required field: 'old_string'"
            if "new_string" not in edit:
                return False, f"Edit[{i}] missing required field: 'new_string'"
            if not isinstance(edit["path"], str):
                return False, f"Edit[{i}].path must be a string"
            if not isinstance(edit["old_string"], str):
                return False, f"Edit[{i}].old_string must be a string"
            if not isinstance(edit["new_string"], str):
                return False, f"Edit[{i}].new_string must be a string"

            # Check if old_string and new_string are the same
            if edit["old_string"] == edit["new_string"]:
                return (
                    False,
                    f"Edit[{i}]: old_string and new_string are the same. No changes to make.",
                )

        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute multi-edit file tool.

        **⚠️ Transactional Behavior**: All edits are atomic - either all succeed or all fail.
        If any edit fails, all changes are rolled back and no files are modified.

        **Args:**
            args: Tool arguments dictionary
                - edits (list, required): List of edit operations. Each edit is a dictionary with:
                    - path (str, required): File path. Relative paths are relative to /workspace.
                    - old_string (str, required): Exact text to replace. Must match exactly.
                      If empty, creates a new file.
                    - new_string (str, required): Replacement text.
                    - replace_all (bool, optional): Replace all occurrences. Default: False.

        **Returns:**
            ToolResult with:
            - ok (bool): True if all edits succeeded (no errors in stderr)
            - stdout (str): Summary of edited files (e.g., "Successfully edited 3 file(s)")
            - stderr (str): Error messages if any (empty string means success)
            - meta (dict): Contains successful_edits, failed_edits, total_edits, edited_files

        **Examples:**
            # Update imports in multiple files atomically
            multi_edit_file(edits=[
                {
                    "path": "src/file1.py",
                    "old_string": "from utils import helper",
                    "new_string": "from utils.helpers import helper"
                },
                {
                    "path": "src/file2.py",
                    "old_string": "from utils import helper",
                    "new_string": "from utils.helpers import helper"
                }
            ])

        **Transaction Phases:**
        1. **Validation phase**: Read all files, check they exist
        2. **Transaction phase**: Apply all edits in memory
        3. **Commit phase**: Write all files (only if all edits succeeded)

        **Error Handling:**
        - If any file read fails → All edits rolled back, error in stderr
        - If any edit fails (old_string not found) → All edits rolled back, error in stderr
        - If any file write fails → Partial success reported, failed files in stderr
        - Success is determined by stderr content, not exit code

        **Best Practices:**
        1. Use when edits must be atomic (all or nothing)
        2. Ensure all old_string values are unique in their respective files
        3. Include sufficient context in old_string for uniqueness
        4. Test with single-file edits first, then combine into multi-edit

        **Note on Trailing Newlines:**
        All files will always end with exactly one newline character after editing.
        """
        edits = args["edits"]

        # Step 1: Read all files first (validation phase)
        file_contents = {}
        read_errors = []

        for i, edit in enumerate(edits):
            path = edit["path"]
            path_escaped = shlex.quote(path)

            # Check if file exists (if old_string is empty, we're creating a new file)
            if edit["old_string"]:
                check_cmd = f"test -f {path_escaped} && echo 'exists' || echo 'not_found'"
                check_result = self._run_command(check_cmd, timeout_sec=5)

                if "not_found" in check_result["stdout"]:
                    read_errors.append(f"Edit[{i}] ({path}): File not found")
                    continue

                # Read file content
                read_cmd = f"cat {path_escaped} 2>/dev/null"
                read_result = self._run_command(read_cmd, timeout_sec=30)

                # Check for read errors in stderr, not exit code
                if read_result.get("stderr", "").strip():
                    read_errors.append(
                        f"Edit[{i}] ({path}): Failed to read file. Error: {read_result.get('stderr', 'Unknown error')}"
                    )
                    continue

                file_contents[path] = read_result.get("stdout", "")
            else:
                # Creating new file
                file_contents[path] = ""

        # If any read errors, return early
        if read_errors:
            return ToolResult(
                ok=False,
                stdout="",
                stderr="\n".join(read_errors),
                meta={"failed_edits": len(read_errors), "total_edits": len(edits)},
            )

        # Step 2: Apply all edits in memory (transaction phase)
        updated_contents = {}
        edit_errors = []

        for i, edit in enumerate(edits):
            path = edit["path"]
            old_string = edit["old_string"]
            new_string = edit["new_string"]
            replace_all = edit.get("replace_all", False)

            # Use updated content if file was already edited in this transaction,
            # otherwise use original content from file
            if path in updated_contents:
                original_content = updated_contents[path]
            else:
                original_content = file_contents[path]

            # Normalize line endings
            original_content = self._normalize_line_endings(original_content)
            old_string_normalized = self._normalize_line_endings(old_string)
            new_string_normalized = self._normalize_line_endings(new_string)

            # Handle edge case for empty new_string
            old_string_for_replace = old_string_normalized
            if new_string_normalized == "" and not old_string_normalized.endswith("\n"):
                if original_content.find(old_string_normalized + "\n") != -1:
                    old_string_for_replace = old_string_normalized + "\n"

            # Perform replacement
            if not old_string:
                # Creating new file
                updated_content = new_string_normalized
            elif replace_all:
                updated_content = original_content.replace(
                    old_string_for_replace, new_string_normalized
                )
            else:
                # Replace first occurrence only
                updated_content = original_content.replace(
                    old_string_for_replace, new_string_normalized, 1
                )

            # Check if content actually changed
            if updated_content == original_content and old_string:
                edit_errors.append(f"Edit[{i}] ({path}): old_string not found or no changes made")
                continue

            updated_contents[path] = updated_content

        # If any edit errors, return early (transaction rollback)
        if edit_errors:
            return ToolResult(
                ok=False,
                stdout="",
                stderr="\n".join(edit_errors),
                meta={"failed_edits": len(edit_errors), "total_edits": len(edits)},
            )

        # Step 3: Write all files (commit phase)
        write_errors = []
        successful_edits = []

        for path, content in updated_contents.items():
            path_escaped = shlex.quote(path)
            # Heredoc automatically adds a newline before FILE_EOF, so we need to handle trailing newlines
            # If content ends with \n, remove it to avoid double newline
            content_for_write = content
            if content_for_write.endswith("\n"):
                content_for_write = content_for_write[:-1]

            write_cmd = f"cat > {path_escaped} <<'FILE_EOF'\n{content_for_write}\nFILE_EOF"
            write_result = self._run_command(write_cmd, timeout_sec=30)

            # Check for write errors in stderr, not exit code
            if write_result.get("stderr", "").strip():
                write_errors.append(
                    f"{path}: Failed to write file. Error: {write_result.get('stderr', 'Unknown error')}"
                )
            else:
                successful_edits.append(path)

        # Generate summary
        if write_errors:
            return ToolResult(
                ok=False,
                stdout=f"Partially successful: {len(successful_edits)}/{len(edits)} files updated.\n",
                stderr="\n".join(write_errors),
                meta={
                    "successful_edits": len(successful_edits),
                    "failed_edits": len(write_errors),
                    "total_edits": len(edits),
                    "edited_files": successful_edits,
                },
            )

        # All successful
        summary = f"Successfully edited {len(edits)} file(s):\n"
        for path in successful_edits:
            summary += f"  - {path}\n"

        return ToolResult(
            ok=True,
            stdout=summary,
            stderr="",
            meta={
                "successful_edits": len(successful_edits),
                "total_edits": len(edits),
                "edited_files": successful_edits,
            },
        )

    def _normalize_line_endings(self, text: str) -> str:
        """Normalize line endings to LF."""
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def _run_command(self, cmd: str, timeout_sec: int = 600) -> Dict[str, Any]:
        """Run a shell command in sandbox."""
        return self.sandbox.exec_shell(
            command=cmd,
            workdir="/workspace",
            timeout_seconds=timeout_sec,
        )
