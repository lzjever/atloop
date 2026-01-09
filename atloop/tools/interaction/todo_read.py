"""Todo read tool for reading task lists."""

from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class TodoReadTool(BaseTool):
    """
    Tool for reading and displaying the current task list from TODO.md.

    **Use cases:**
    - Checking current task status
    - Reviewing progress on multi-step tasks
    - Understanding what work is in progress
    - Planning next steps based on current status
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize todo read tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox
        self.todo_file = "TODO.md"

    @property
    def name(self) -> str:
        """Tool name."""
        return "todo_read"

    @property
    def description(self) -> str:
        """Tool description."""
        return "读取任务列表（解析 TODO.md）\n  参数: 无\n  示例: todo_read()\n  说明: 读取并显示当前任务列表的状态。"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        # No required arguments
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute todo read tool to read and display TODO.md.

        **Args:**
            args: Tool arguments dictionary (no arguments required)

        **Returns:**
            ToolResult with:
            - ok (bool): True if TODO.md was read successfully (no errors in stderr)
            - stdout (str): Formatted TODO list with tasks grouped by status
            - stderr (str): Error messages if any (empty string means success)
            - meta (dict): Contains todo_file, todo_count, pending, in_progress, completed

        **Examples:**
            # Read current TODO list
            todo_read()

        **Output Format:**
        Tasks are grouped by status and displayed as:
        ```
        # TODO List (3 task(s))

        ## In Progress
        1. Task 1 (Running task 1)

        ## Pending
        1. Task 2 (Will run task 2)

        ## Completed (1)
        1. Task 3

        Summary: 1 pending, 1 in progress, 1 completed
        ```

        **Behavior:**
        - If TODO.md doesn't exist: Returns ok=True with message to use todo_write
        - If TODO.md exists but is empty: Returns ok=True with message
        - If TODO.md has tasks: Returns formatted list grouped by status
        - Only shows first 5 completed tasks (to avoid clutter)

        **Error Handling:**
        - Success is determined by stderr content, not exit code
        - If stderr is empty, the operation succeeded
        - Check stderr for specific error messages if ok=False
        """
        todo_file_path = self.todo_file

        # Check if TODO.md exists
        check_cmd = f"test -f {todo_file_path} && echo 'exists' || echo 'not_found'"
        check_result = self._run_command(check_cmd, timeout_sec=5)

        if "not_found" in check_result.get("stdout", ""):
            return ToolResult(
                ok=True,
                stdout="No TODO.md file found. Use todo_write to create a task list.",
                stderr="",
                meta={"todo_file": todo_file_path, "exists": False},
            )

        # Read TODO.md
        read_cmd = f"cat {todo_file_path} 2>/dev/null"
        read_result = self._run_command(read_cmd, timeout_sec=5)

        # Check for read errors in stderr, not exit code
        if read_result.get("stderr", "").strip():
            return ToolResult(
                ok=False,
                stdout="",
                stderr=f"Failed to read TODO.md: {read_result.get('stderr', 'Unknown error')}",
                meta={"todo_file": todo_file_path},
            )

        content = read_result.get("stdout", "")

        # Parse and format
        todos = self._parse_markdown_todos(content)

        if not todos:
            return ToolResult(
                ok=True,
                stdout="TODO.md exists but contains no tasks.",
                stderr="",
                meta={"todo_file": todo_file_path, "todo_count": 0},
            )

        # Generate formatted output
        output = f"# TODO List ({len(todos)} task(s))\n\n"

        # Group by status
        pending = [t for t in todos if t["status"] == "pending"]
        in_progress = [t for t in todos if t["status"] == "in_progress"]
        completed = [t for t in todos if t["status"] == "completed"]

        if in_progress:
            output += "## In Progress\n"
            for i, todo in enumerate(in_progress, 1):
                output += f"{i}. {todo['content']} ({todo.get('activeForm', todo['content'])})\n"
            output += "\n"

        if pending:
            output += "## Pending\n"
            for i, todo in enumerate(pending, 1):
                output += f"{i}. {todo['content']} ({todo.get('activeForm', todo['content'])})\n"
            output += "\n"

        if completed:
            output += f"## Completed ({len(completed)})\n"
            for i, todo in enumerate(completed[:5], 1):  # Show first 5
                output += f"{i}. {todo['content']}\n"
            if len(completed) > 5:
                output += f"... and {len(completed) - 5} more completed tasks\n"
            output += "\n"

        output += f"\nSummary: {len(pending)} pending, {len(in_progress)} in progress, {len(completed)} completed"

        return ToolResult(
            ok=True,
            stdout=output,
            stderr="",
            meta={
                "todo_file": todo_file_path,
                "todo_count": len(todos),
                "pending": len(pending),
                "in_progress": len(in_progress),
                "completed": len(completed),
            },
        )

    def _parse_markdown_todos(self, content: str) -> list:
        """Parse markdown TODO format."""
        todos = []
        lines = content.split("\n")
        current_todo = None

        for line in lines:
            line = line.strip()
            if line.startswith("- [ ]") or line.startswith("- [x]"):
                # New todo item
                if current_todo:
                    todos.append(current_todo)

                status = "completed" if line.startswith("- [x]") else "pending"
                content_text = line[5:].strip()

                # Extract activeForm if present in parentheses
                active_form = content_text
                if "(" in content_text and ")" in content_text:
                    # Format: "content (activeForm)"
                    parts = content_text.rsplit("(", 1)
                    if len(parts) == 2:
                        content_text = parts[0].strip()
                        active_form = parts[1].rstrip(")").strip()

                current_todo = {
                    "content": content_text,
                    "activeForm": active_form,
                    "status": status,
                }
            elif current_todo and line and not line.startswith("#"):
                # Continuation of current todo
                current_todo["content"] += " " + line

        if current_todo:
            todos.append(current_todo)

        return todos

    def _run_command(self, cmd: str, timeout_sec: int = 600) -> Dict[str, Any]:
        """Run a shell command in sandbox."""
        return self.sandbox.exec_shell(
            command=cmd,
            workdir="/workspace",
            timeout_seconds=timeout_sec,
        )
