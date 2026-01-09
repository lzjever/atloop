"""Glob tool for file matching with gitignore-style patterns."""

from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class GlobFilesTool(BaseTool):
    """
    Tool for finding files using gitignore-style glob patterns.

    **Features:**
    - Supports common glob patterns (*, **)
    - Recursive directory searching
    - File filtering by extension or pattern

    **Use cases:**
    - Finding all Python files: `*.py`
    - Finding all test files: `test_*.py`
    - Finding files recursively: `**/*.js`
    - Listing files in a directory: `dir/*.txt`
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize glob files tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        """Tool name."""
        return "glob"

    @property
    def description(self) -> str:
        """Tool description."""
        return "文件匹配工具（支持 Gitignore 样式的 glob 模式）"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "pattern" not in args:
            return False, "Missing required argument: 'pattern'"
        if not isinstance(args["pattern"], str):
            return False, "Argument 'pattern' must be a string"
        if "max_results" in args and not isinstance(args.get("max_results"), int):
            return False, "Argument 'max_results' must be an integer"
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute glob tool to find files matching a pattern.

        **Args:**
            args: Tool arguments dictionary
                - pattern (str, required): Glob pattern to match files. Supports:
                  - `*.py`: Matches all .py files in current directory
                  - `**/*.py`: Matches all .py files recursively
                  - `test_*.py`: Matches files starting with "test_"
                  - `dir/*.txt`: Matches .txt files in "dir" directory
                - max_results (int, optional): Maximum number of results to return.
                  Default: 100. Use this to limit output for very large matches.

        **Returns:**
            ToolResult with:
            - ok (bool): True if pattern was executed successfully (no errors in stderr)
            - stdout (str): Formatted list of matched files, one per line
            - stderr (str): Error messages if any (empty string means success)
            - meta (dict): Contains pattern, max_results, matched_count, matched_files

        **Examples:**
            # Find all Python files
            glob(pattern="*.py")

            # Find all Python files recursively
            glob(pattern="**/*.py")

            # Find test files
            glob(pattern="test_*.py")

            # Find files in specific directory
            glob(pattern="src/*.py")

            # Limit results
            glob(pattern="*.py", max_results=10)

        **Pattern Support:**
        - `*`: Matches any characters (except path separator)
        - `**`: Matches any characters including path separators (recursive)
        - Directory patterns: `dir/*.ext` matches files in "dir" directory
        - Leading `./` is optional and ignored

        **Error Handling:**
        - Success is determined by stderr content, not exit code
        - If stderr is empty, the operation succeeded
        - Empty results (no matches) is considered success (ok=True)
        - Check stderr for specific error messages if ok=False
        """
        pattern = args["pattern"]
        max_results = args.get("max_results", 100)

        # Use find command with glob pattern matching
        # Support common glob patterns:
        # - *.py: matches all .py files
        # - **/*.py: matches all .py files recursively
        # - test_*.py: matches files starting with test_
        # - {*.py,*.js}: multiple patterns (not directly supported, but can be handled)

        # Convert glob pattern to find command
        # For simple patterns, use find with -name
        # For ** patterns, use find recursively

        if "**" in pattern:
            # Recursive pattern: **/*.py -> find . -name "*.py"
            # Remove **/ prefix if present
            name_pattern = pattern.replace("**/", "").replace("./", "")
            cmd = f"find . -type f -name {self._quote_pattern(name_pattern)} 2>/dev/null | head -n {max_results}"
        elif pattern.startswith("./"):
            # Pattern like ./dir/*.py
            pattern_clean = pattern[2:]  # Remove ./
            if "/" in pattern_clean:
                # Has directory: dir/*.py
                parts = pattern_clean.split("/", 1)
                dir_part = parts[0]
                name_pattern = parts[1]
                cmd = f"find ./{dir_part} -maxdepth 1 -type f -name {self._quote_pattern(name_pattern)} 2>/dev/null | head -n {max_results}"
            else:
                # Just filename pattern: *.py
                cmd = f"find . -maxdepth 1 -type f -name {self._quote_pattern(pattern_clean)} 2>/dev/null | head -n {max_results}"
        else:
            # Simple pattern: *.py, test_*.py
            # Check if pattern contains directory separator
            if "/" in pattern:
                # Pattern like dir/*.py
                parts = pattern.split("/", 1)
                dir_part = parts[0]
                name_pattern = parts[1]
                cmd = f"find ./{dir_part} -maxdepth 1 -type f -name {self._quote_pattern(name_pattern)} 2>/dev/null | head -n {max_results}"
            else:
                # Just filename pattern
                cmd = f"find . -maxdepth 1 -type f -name {self._quote_pattern(pattern)} 2>/dev/null | head -n {max_results}"

        result = self._run_command(cmd, timeout_sec=30)

        # Check for errors in stderr, not exit code
        stderr = result.get("stderr", "")
        if stderr.strip():
            return ToolResult(
                ok=False,
                stdout="",
                stderr=stderr or "Failed to execute glob pattern",
                meta={"pattern": pattern, "max_results": max_results},
            )

        # Parse results - each line is a file path
        stdout = result.get("stdout", "")
        matched_files = [line.strip() for line in stdout.split("\n") if line.strip()]

        # Remove leading ./ if present
        matched_files = [f.lstrip("./") for f in matched_files]

        # Format output
        if matched_files:
            output = f"Found {len(matched_files)} file(s) matching pattern '{pattern}':\n"
            for file_path in matched_files:
                output += f"  - {file_path}\n"
        else:
            output = f"No files found matching pattern '{pattern}'"

        return ToolResult(
            ok=True,
            stdout=output,
            stderr=stderr,
            meta={
                "pattern": pattern,
                "max_results": max_results,
                "matched_count": len(matched_files),
                "matched_files": matched_files,
            },
        )

    def _quote_pattern(self, pattern: str) -> str:
        """Quote pattern for shell command."""
        import shlex

        return shlex.quote(pattern)

    def _run_command(self, cmd: str, timeout_sec: int = 600) -> Dict[str, Any]:
        """Run a shell command in sandbox."""
        return self.sandbox.exec_shell(
            command=cmd,
            workdir="/workspace",
            timeout_seconds=timeout_sec,
        )
