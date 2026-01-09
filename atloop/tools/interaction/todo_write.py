"""Todo write tool for managing task lists."""

import json
from typing import Any, Dict, List, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class TodoWriteTool(BaseTool):
    """
    Tool for creating and managing task lists in TODO.md format.

    **Use cases:**
    - Tracking progress on complex, multi-step tasks
    - Managing task status (pending, in_progress, completed)
    - Organizing work into manageable chunks
    - Providing visibility into current work status

    **Task statuses:**
    - `pending`: Task not yet started
    - `in_progress`: Task currently being worked on
    - `completed`: Task finished

    **Best practices:**
    - At least one task should be in_progress at any time
    - Use activeForm to describe what's happening (e.g., "Running tests")
    - Update status as work progresses
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize todo write tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox
        self.todo_file = "TODO.md"

    @property
    def name(self) -> str:
        """Tool name."""
        return "todo_write"

    @property
    def description(self) -> str:
        """Tool description."""
        return "创建和管理任务列表（TODO.md 格式）\n  参数: todos (array): 任务数组，每个任务包含:\n        - content (string): 任务内容（必需，命令式，如 'Run tests'）\n        - activeForm (string): 进行时形式（必需，如 'Running tests'）\n        - status (string): 任务状态 - 'pending'（未开始）、'in_progress'（进行中）、'completed'（已完成）\n  示例: todo_write(todos=[{'content': 'Run tests', 'activeForm': 'Running tests', 'status': 'in_progress'}])\n  说明: 用于跟踪复杂任务的进度。至少应有一个任务处于 in_progress 状态。"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "todos" not in args:
            return False, "Missing required argument: 'todos'"
        if not isinstance(args["todos"], list):
            return False, "Argument 'todos' must be a list"

        for i, todo in enumerate(args["todos"]):
            if not isinstance(todo, dict):
                return False, f"Todo[{i}] must be a dictionary"
            if "content" not in todo:
                return False, f"Todo[{i}] missing required field: 'content'"
            if "activeForm" not in todo:
                return False, f"Todo[{i}] missing required field: 'activeForm'"
            if "status" not in todo:
                return False, f"Todo[{i}] missing required field: 'status'"
            if todo["status"] not in ["pending", "in_progress", "completed"]:
                return (
                    False,
                    f"Todo[{i}] invalid status: must be 'pending', 'in_progress', or 'completed'",
                )

        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute todo write tool to create or update TODO.md.

        **Args:**
            args: Tool arguments dictionary
                - todos (list, required): List of todo items. Each item is a dictionary with:
                    - content (str, required): Task content in imperative form.
                      Example: "Run tests", "Fix bug", "Write documentation"
                    - activeForm (str, required): Present continuous form describing the action.
                      Example: "Running tests", "Fixing bug", "Writing documentation"
                    - status (str, required): Task status. Must be one of:
                      - "pending": Task not yet started
                      - "in_progress": Task currently being worked on
                      - "completed": Task finished

        **Returns:**
            ToolResult with:
            - ok (bool): True if TODO.md was written successfully (no errors in stderr)
            - stdout (str): Summary of updated TODO list with counts by status
            - stderr (str): Error messages if any (empty string means success)
            - meta (dict): Contains todo_file, todo_count, pending, in_progress, completed

        **Examples:**
            # Create initial TODO list
            todo_write(todos=[
                {
                    "content": "Set up project structure",
                    "activeForm": "Setting up project structure",
                    "status": "in_progress"
                },
                {
                    "content": "Write unit tests",
                    "activeForm": "Writing unit tests",
                    "status": "pending"
                }
            ])

            # Update TODO list (replaces entire list)
            todo_write(todos=[
                {
                    "content": "Set up project structure",
                    "activeForm": "Setting up project structure",
                    "status": "completed"
                },
                {
                    "content": "Write unit tests",
                    "activeForm": "Writing unit tests",
                    "status": "in_progress"
                }
            ])

        **Important Notes:**
        - This tool **replaces** the entire TODO.md file with the new todos list
        - To update a single task, read current todos, modify, then write back
        - At least one task should be in_progress (warning shown if none)
        - TODO.md is created in the workspace root directory

        **File Format:**
        The tool generates markdown format:
        ```markdown
        # TODO

        ## In Progress
        - [ ] Task 1 (Running task 1)

        ## Pending
        - [ ] Task 2 (Will run task 2)

        ## Completed
        - [x] Task 3
        ```

        **Error Handling:**
        - Success is determined by stderr content, not exit code
        - If stderr is empty, the operation succeeded
        - Check stderr for specific error messages if ok=False
        """
        todos = args["todos"]

        # Read existing todos if file exists
        todo_file_path = self.todo_file

        # Check if TODO.md exists
        check_cmd = f"test -f {todo_file_path} && echo 'exists' || echo 'not_found'"
        check_result = self._run_command(check_cmd, timeout_sec=5)

        if "exists" in check_result.get("stdout", ""):
            # Read existing todos
            read_cmd = f"cat {todo_file_path} 2>/dev/null"
            read_result = self._run_command(read_cmd, timeout_sec=5)
            if not read_result.get("stderr", "").strip():
                try:
                    # Try to parse as JSON first (for structured format)
                    content = read_result.get("stdout", "").strip()
                    if content.startswith("{"):
                        json.loads(content).get("todos", [])
                    else:
                        # Parse markdown format
                        self._parse_markdown_todos(content)
                except (json.JSONDecodeError, ValueError):
                    # If parsing fails, start fresh
                    pass

        # Merge with existing todos (simple merge strategy)
        # For now, replace all todos with new ones
        # In a more sophisticated implementation, we could merge by content/activeForm

        # Generate TODO.md content
        todo_content = self._generate_todo_markdown(todos)

        # Write TODO.md
        write_cmd = f"cat > {todo_file_path} <<'TODO_EOF'\n{todo_content}\nTODO_EOF"
        write_result = self._run_command(write_cmd, timeout_sec=10)

        # Check for write errors in stderr, not exit code
        if write_result.get("stderr", "").strip():
            return ToolResult(
                ok=False,
                stdout="",
                stderr=f"Failed to write TODO.md: {write_result.get('stderr', 'Unknown error')}",
                meta={"todo_file": todo_file_path},
            )

        # Generate summary
        pending_count = sum(1 for t in todos if t["status"] == "pending")
        in_progress_count = sum(1 for t in todos if t["status"] == "in_progress")
        completed_count = sum(1 for t in todos if t["status"] == "completed")

        summary = f"Updated TODO.md with {len(todos)} task(s):\n"
        summary += f"  - Pending: {pending_count}\n"
        summary += f"  - In Progress: {in_progress_count}\n"
        summary += f"  - Completed: {completed_count}\n"

        if in_progress_count == 0 and len(todos) > 0:
            summary += "\n⚠️  Warning: No tasks are in_progress. Consider marking at least one task as in_progress."

        return ToolResult(
            ok=True,
            stdout=summary,
            stderr="",
            meta={
                "todo_file": todo_file_path,
                "todo_count": len(todos),
                "pending": pending_count,
                "in_progress": in_progress_count,
                "completed": completed_count,
            },
        )

    def _parse_markdown_todos(self, content: str) -> List[Dict[str, Any]]:
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
                current_todo = {
                    "content": content_text,
                    "activeForm": content_text,  # Default to same as content
                    "status": status,
                }
            elif current_todo and line:
                # Continuation of current todo
                current_todo["content"] += " " + line

        if current_todo:
            todos.append(current_todo)

        return todos

    def _generate_todo_markdown(self, todos: List[Dict[str, Any]]) -> str:
        """Generate markdown TODO format."""
        lines = ["# TODO\n", ""]

        # Group by status
        pending = [t for t in todos if t["status"] == "pending"]
        in_progress = [t for t in todos if t["status"] == "in_progress"]
        completed = [t for t in todos if t["status"] == "completed"]

        if in_progress:
            lines.append("## In Progress\n")
            for todo in in_progress:
                lines.append(f"- [ ] {todo['content']} ({todo['activeForm']})")
            lines.append("")

        if pending:
            lines.append("## Pending\n")
            for todo in pending:
                lines.append(f"- [ ] {todo['content']} ({todo['activeForm']})")
            lines.append("")

        if completed:
            lines.append("## Completed\n")
            for todo in completed:
                lines.append(f"- [x] {todo['content']}")
            lines.append("")

        return "\n".join(lines)

    def _run_command(self, cmd: str, timeout_sec: int = 600) -> Dict[str, Any]:
        """Run a shell command in sandbox."""
        return self.sandbox.exec_shell(
            command=cmd,
            workdir="/workspace",
            timeout_seconds=timeout_sec,
        )
