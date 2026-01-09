"""Enhanced search tool using grep with regex, context lines, and file filtering."""

import shlex
from typing import Any, Dict, Optional

from atloop.runtime.sandbox_adapter import SandboxAdapter
from atloop.tools.base import BaseTool, ToolResult


class SearchTool(BaseTool):
    """
    Enhanced tool for searching file contents using grep with regex, context lines, and file filtering.

    **Features:**
    - Full regex pattern support
    - Context lines (before/after matches)
    - File filtering by glob pattern
    - Multiple output modes (content, files, count)
    - Case-insensitive search option

    **Use cases:**
    - Finding function definitions: `search('def function_name')`
    - Finding imports: `search('^import |^from ')`
    - Finding specific patterns: `search('TODO|FIXME')`
    - Searching in specific file types: `search('pattern', glob='*.py')`
    """

    def __init__(self, sandbox: SandboxAdapter):
        """
        Initialize search tool.

        Args:
            sandbox: Sandbox adapter instance
        """
        self.sandbox = sandbox

    @property
    def name(self) -> str:
        """Tool name."""
        return "search"

    @property
    def description(self) -> str:
        """Tool description."""
        return "强大的文件内容搜索工具（支持正则表达式、上下文行、文件过滤）\n  参数: query (string): 搜索查询（正则表达式，必需）\n        glob (string, 可选): 文件过滤模式（如 '*.py', '**/*.js'）\n        output_mode (string, 可选): 输出模式 - 'content'（显示匹配行，默认）、'files_with_matches'（仅文件路径）、'count'（匹配计数）\n        -A (int, 可选): 显示匹配行后的行数\n        -B (int, 可选): 显示匹配行前的行数\n        -C (int, 可选): 显示匹配行前后的行数\n        -i (bool, 可选): 忽略大小写（默认 false）\n        -n (bool, 可选): 显示行号（默认 true）\n        max_results (int, 可选): 最大结果数（默认 50）"

    def validate_args(self, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments."""
        if "query" not in args:
            return False, "Missing required argument: 'query'"
        if not isinstance(args["query"], str):
            return False, "Argument 'query' must be a string"
        if "output_mode" in args and args["output_mode"] not in [
            "content",
            "files_with_matches",
            "count",
        ]:
            return (
                False,
                "Argument 'output_mode' must be one of: 'content', 'files_with_matches', 'count'",
            )
        if "-A" in args and not isinstance(args["-A"], int):
            return False, "Argument '-A' must be an integer"
        if "-B" in args and not isinstance(args["-B"], int):
            return False, "Argument '-B' must be an integer"
        if "-C" in args and not isinstance(args["-C"], int):
            return False, "Argument '-C' must be an integer"
        if "-i" in args and not isinstance(args["-i"], bool):
            return False, "Argument '-i' must be a boolean"
        if "-n" in args and not isinstance(args["-n"], bool):
            return False, "Argument '-n' must be a boolean"
        if "max_results" in args and not isinstance(args.get("max_results"), int):
            return False, "Argument 'max_results' must be an integer"
        return True, None

    def execute(self, args: Dict[str, Any]) -> ToolResult:
        """
        Execute enhanced search tool to find patterns in files.

        **Args:**
            args: Tool arguments dictionary
                - query (str, required): Search query as regex pattern. Supports full regex syntax.
                  Examples: "def function", "^import ", "TODO|FIXME", "class \\w+"
                - glob (str, optional): Glob pattern to filter files. Examples: "*.py", "**/*.js"
                - output_mode (str, optional): Output mode. Default: "content"
                  - "content": Show matching lines with context (default)
                  - "files_with_matches": Show only file paths that contain matches
                  - "count": Show match count per file
                - -A (int, optional): Number of lines to show after each match
                - -B (int, optional): Number of lines to show before each match
                - -C (int, optional): Number of lines to show before and after each match
                - -i (bool, optional): Case-insensitive search. Default: False
                - -n (bool, optional): Show line numbers. Default: True
                - max_results (int, optional): Maximum number of results to return.
                  Default: 50. Limits output for very large result sets.

        **Returns:**
            ToolResult with:
            - ok (bool): True if search executed successfully (no errors in stderr)
            - stdout (str): Search results (matching lines, file paths, or counts)
            - stderr (str): Error messages if any (empty string means success)
            - meta (dict): Contains query, glob, output_mode, max_results, cmd

        **Examples:**
            # Find function definitions
            search(query="def \\w+", glob="*.py")

            # Find imports with context
            search(query="^import |^from ", glob="*.py", -C=2)

            # Find TODO comments (case-insensitive)
            search(query="TODO|FIXME", -i=True)

            # Find files containing pattern (without showing content)
            search(query="def main", output_mode="files_with_matches")

            # Count matches per file
            search(query="class \\w+", output_mode="count")

        **Regex Pattern Tips:**
        - Use `^` for start of line: `^def` matches "def" at line start
        - Use `$` for end of line: `import$` matches "import" at line end
        - Use `|` for alternation: `TODO|FIXME` matches either
        - Use `\\w+` for word characters: `def \\w+` matches "def function_name"
        - Escape special chars: `\\.` matches literal dot

        **Context Lines:**
        - Use `-C=3` to show 3 lines before and after each match
        - Use `-B=5` to show 5 lines before each match
        - Use `-A=2` to show 2 lines after each match
        - Context helps understand code structure around matches

        **Error Handling:**
        - Success is determined by stderr content, not exit code
        - If stderr is empty, the search succeeded
        - No matches found is considered success (ok=True, empty stdout)
        - Check stderr for specific error messages if ok=False
        """
        query = args["query"]
        glob = args.get("glob")
        output_mode = args.get("output_mode", "content")
        before = args.get("-B")
        after = args.get("-A")
        context = args.get("-C")
        case_insensitive = args.get("-i", False)
        line_numbers = args.get("-n", True)
        max_results = args.get("max_results", 50)

        query_escaped = shlex.quote(query)

        # Build grep command with enhanced options
        cmd_parts = ["grep", "-r"]

        # Add case insensitive flag
        if case_insensitive:
            cmd_parts.append("-i")

        # Add line numbers (only for content mode)
        if line_numbers and output_mode == "content":
            cmd_parts.append("-n")

        # Add context lines (only for content mode)
        if output_mode == "content":
            if context is not None:
                cmd_parts.extend(["-C", str(context)])
            else:
                if before is not None:
                    cmd_parts.extend(["-B", str(before)])
                if after is not None:
                    cmd_parts.extend(["-A", str(after)])

        # Add file filtering
        if glob:
            if "**" in glob:
                # Recursive pattern: use find + grep
                find_pattern = glob.replace("**/", "").replace("./", "")
                cmd_parts.append("--include")
                cmd_parts.append(shlex.quote(find_pattern))
            else:
                include_pattern = glob.lstrip("./")
                cmd_parts.append("--include")
                cmd_parts.append(shlex.quote(include_pattern))

        # Add output mode flags
        if output_mode == "files_with_matches":
            cmd_parts.append("-l")  # List files only
        elif output_mode == "count":
            cmd_parts.append("-c")  # Count matches

        # Add regex pattern
        cmd_parts.append("-E")  # Extended regex
        cmd_parts.append(query_escaped)

        # Add search path
        cmd_parts.append(".")

        # Build final command
        cmd = " ".join(cmd_parts)

        # Add result limiting
        if output_mode == "content":
            # Limit output lines
            cmd = f"{cmd} 2>/dev/null | head -n {max_results}"
        elif output_mode == "files_with_matches":
            # Limit file count
            cmd = f"{cmd} 2>/dev/null | head -n {max_results}"
        else:  # count
            # Limit count entries
            cmd = f"{cmd} 2>/dev/null | head -n {max_results}"

        result = self.sandbox.exec_shell(
            command=cmd,
            workdir="/workspace",
            timeout_seconds=60,
        )

        # Determine success based on stderr content, not exit code
        stderr = result.get("stderr", "")
        ok = not bool(stderr.strip())  # Success if no error messages in stderr

        return ToolResult(
            ok=ok,
            stdout=result.get("stdout", ""),
            stderr=stderr,
            meta={
                "query": query,
                "glob": glob,
                "output_mode": output_mode,
                "max_results": max_results,
                "cmd": cmd,
            },
        )
