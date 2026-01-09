"""Tool runtime for executing tools in sandbox (legacy compatibility layer)."""

from typing import List, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import ToolResult
from atloop.tools.registry import ToolRegistry


class ToolRuntime:
    """
    Tool runtime for executing tools in sandbox.

    This is a legacy compatibility layer. New code should use ToolRegistry directly.
    """

    def __init__(self, sandbox: SandboxAdapter, skill_loader=None):
        """
        Initialize tool runtime.

        Args:
            sandbox: Sandbox adapter instance
            skill_loader: Optional skill loader instance for read_skill_file tool
        """
        self.sandbox = sandbox
        self.registry = ToolRegistry(sandbox, skill_loader=skill_loader)

    def run(self, cmd: str, timeout_sec: int = 600) -> ToolResult:
        """
        Execute shell command.

        Args:
            cmd: Shell command to execute
            timeout_sec: Command timeout in seconds

        Returns:
            ToolResult instance
        """
        return self.registry.execute("run", {"cmd": cmd, "timeout_sec": timeout_sec})

    def list_tree(
        self, max_depth: int = 4, ignore_patterns: Optional[List[str]] = None
    ) -> ToolResult:
        """
        List file tree.

        Args:
            max_depth: Maximum depth to traverse
            ignore_patterns: Patterns to ignore (e.g., ["node_modules", ".git"])

        Returns:
            ToolResult with file tree
        """
        if ignore_patterns is None:
            ignore_patterns = ["node_modules", "dist", "build", ".git", "__pycache__"]

        # Build find command with ignore patterns
        import shlex

        ignore_parts = []
        for pattern in ignore_patterns:
            ignore_parts.append(f"-name {shlex.quote(pattern)} -prune")

        if ignore_parts:
            ignore_expr = " -o ".join(ignore_parts)
            cmd = (
                f"find . -maxdepth {max_depth} \\( {ignore_expr} -o -type f -print \\) | head -100"
            )
        else:
            cmd = f"find . -maxdepth {max_depth} -type f | head -100"

        return self.run(cmd, timeout_sec=60)

    def search(self, query: str, glob: Optional[str] = None, max_results: int = 50) -> ToolResult:
        """
        Search using grep.

        Args:
            query: Search query (treated as regex pattern)
            glob: Glob pattern to filter files (e.g., "*.py", "**/*.js")
            max_results: Maximum number of results

        Returns:
            ToolResult with search results
        """
        return self.registry.execute(
            "search",
            {
                "query": query,
                "glob": glob,
                "max_results": max_results,
            },
        )

    def read_file(
        self,
        path: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> ToolResult:
        """
        Read file lines (legacy method - use ToolRegistry.execute("read_file", ...) instead).

        Args:
            path: File path
            start_line: Start line number (1-indexed) - legacy parameter
            end_line: End line number (1-indexed) - legacy parameter
            offset: Line number to start reading from (1-indexed) - new parameter
            limit: Number of lines to read - new parameter

        Returns:
            ToolResult with file content
        """
        args = {"path": path}
        if offset is not None:
            args["offset"] = offset
        if limit is not None:
            args["limit"] = limit
        elif end_line is not None:
            # Legacy support: convert end_line to limit
            args["offset"] = start_line
            args["limit"] = end_line - start_line + 1

        return self.registry.execute("read_file", args)

    def write_file(self, path: str, content: str) -> ToolResult:
        """
        Write file (legacy method - use ToolRegistry.execute("write_file", ...) instead).

        Args:
            path: File path
            content: File content

        Returns:
            ToolResult
        """
        return self.registry.execute("write_file", {"path": path, "content": content})

    def git_diff(self) -> ToolResult:
        """
        Get git diff (legacy method - use ToolRegistry.execute("run", {"cmd": "git diff"}) instead).

        Returns:
            ToolResult with git diff output
        """
        return self.run("git diff", timeout_sec=30)

    def apply_patch(self, patch: str) -> ToolResult:
        """
        Apply patch (legacy method - use ToolRegistry.execute("run", {"cmd": "git apply"}) instead).

        Args:
            patch: Patch content

        Returns:
            ToolResult
        """
        # Write patch to temporary file and apply
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
            f.write(patch)
            patch_file = f.name

        try:
            # Use git apply or patch command
            result = self.run(
                f"git apply {patch_file} 2>&1 || patch -p1 < {patch_file} 2>&1", timeout_sec=30
            )
        finally:
            import os

            try:
                os.unlink(patch_file)
            except Exception:
                pass

        return result
