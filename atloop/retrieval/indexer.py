"""Workspace indexer for file tree and search."""

from typing import Any, Dict, List, Optional

from atloop.runtime import ToolResult, ToolRuntime


class WorkspaceIndexer:
    """Workspace indexer for file tree and search."""

    def __init__(self, tool_runtime: ToolRuntime):
        """
        Initialize workspace indexer.

        Args:
            tool_runtime: Tool runtime instance
        """
        self.tool_runtime = tool_runtime

    def bootstrap(self) -> Dict[str, Any]:
        """
        Bootstrap workspace (initial discovery).

        Returns:
            Dictionary with workspace information
        """
        # List file tree
        tree_result = self.tool_runtime.list_tree(max_depth=4)

        # Get git status
        git_status_result = self.tool_runtime.run(
            "git status --porcelain=v1 2>/dev/null || echo 'not-git'", timeout_sec=10
        )

        return {
            "file_tree": tree_result.stdout if tree_result.ok else "",
            "git_status": git_status_result.stdout if git_status_result.ok else "",
        }

    def list_tree(
        self, max_depth: int = 4, ignore_patterns: Optional[List[str]] = None
    ) -> ToolResult:
        """
        List file tree.

        Args:
            max_depth: Maximum depth
            ignore_patterns: Patterns to ignore

        Returns:
            ToolResult with file tree
        """
        return self.tool_runtime.list_tree(max_depth=max_depth, ignore_patterns=ignore_patterns)

    def search(self, query: str, glob: Optional[str] = None, max_results: int = 50) -> ToolResult:
        """
        Search using grep (common Linux tool).

        Args:
            query: Search query
            glob: Glob pattern
            max_results: Maximum results

        Returns:
            ToolResult with search results
        """
        return self.tool_runtime.search(query=query, glob=glob, max_results=max_results)

    def read_snippets(
        self,
        file_paths: List[str],
        context_lines: int = 80,
        max_total_size: int = 80 * 1024,  # 80KB
        max_file_lines: int = 300,
    ) -> List[Dict[str, Any]]:
        """
        Read file snippets with context.

        Args:
            file_paths: List of file paths to read
            context_lines: Number of context lines around matches
            max_total_size: Maximum total size in bytes
            max_file_lines: Maximum lines per file

        Returns:
            List of file snippet dictionaries
        """
        snippets = []
        total_size = 0

        for file_path in file_paths:
            if total_size >= max_total_size:
                break

            # Read file using system command
            import shlex

            file_path_escaped = shlex.quote(file_path)
            result = self.tool_runtime.run(
                f"head -n {max_file_lines} {file_path_escaped} 2>/dev/null || cat {file_path_escaped} 2>/dev/null",
                timeout_sec=10,
            )

            if result.ok:
                content = result.stdout
                content_size = len(content.encode("utf-8"))

                if total_size + content_size > max_total_size:
                    # Truncate if needed
                    remaining = max_total_size - total_size
                    content = content[:remaining]
                    content_size = remaining

                snippets.append(
                    {
                        "path": file_path,
                        "content": content,
                        "size": content_size,
                        "lines": len(content.splitlines()),
                    }
                )

                total_size += content_size

        return snippets

    def extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text (simple implementation).

        Args:
            text: Text to extract keywords from

        Returns:
            List of keywords
        """
        # Simple keyword extraction: function names, class names, error messages
        import re

        keywords = []

        # Function/class names (CamelCase, snake_case)
        patterns = [
            r"\b[A-Z][a-zA-Z0-9]*\b",  # CamelCase
            r"\b[a-z_][a-z0-9_]*\b",  # snake_case
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            keywords.extend(matches)

        # Error messages
        error_patterns = [
            r"Error:\s*([^\n]+)",
            r"Exception:\s*([^\n]+)",
            r"FAILED\s+([^\n]+)",
        ]

        for pattern in error_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            keywords.extend(matches)

        # Remove duplicates and common words
        common_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
        }

        keywords = [k for k in set(keywords) if len(k) > 2 and k.lower() not in common_words]

        return keywords[:20]  # Limit to 20 keywords
