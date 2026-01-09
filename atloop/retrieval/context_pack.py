"""Context pack builder."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from atloop.config.limits import (
    CONTEXT_PACK_MAX_SIZE,
    DIFF_LIMIT,
    RECENT_ERROR_LIMIT_FILE_CONTENT,
    RECENT_ERROR_LIMIT_NORMAL,
    TEST_RESULTS_LIMIT_CONTEXT,
    is_file_content,
)
from atloop.retrieval.indexer import WorkspaceIndexer
from atloop.retrieval.project_profile import ProjectProfile


@dataclass
class ContextPack:
    """Context pack for LLM input."""

    goal: str
    constraints: List[str]
    project_profile: str
    relevant_files: str
    recent_error: str
    current_diff: str
    test_results: Optional[str] = None  # Latest test/verification results
    verification_success: Optional[bool] = None  # Whether latest verification passed
    memory_summary: Optional[str] = None

    def to_string(self, max_size: int = CONTEXT_PACK_MAX_SIZE) -> str:
        """
        Convert to string representation.

        Args:
            max_size: Maximum size in bytes

        Returns:
            String representation
        """
        parts = []

        # Goal & Constraints
        parts.append("## Task Goal")
        parts.append(self.goal)
        parts.append("")

        if self.constraints:
            parts.append("## Constraints")
            for constraint in self.constraints:
                parts.append(f"- {constraint}")
            parts.append("")

        # Project Profile
        parts.append("## Project Information")
        parts.append(self.project_profile)
        parts.append("")

        # Relevant Files
        parts.append("## Relevant File Snippets")
        parts.append(self.relevant_files)
        parts.append("")

        # Recent Error
        if self.recent_error and self.recent_error != "None":
            parts.append("## Recent Error")
            parts.append(self.recent_error)
            parts.append("")

        # Current Diff
        if self.current_diff and self.current_diff != "No changes":
            parts.append("## Current Diff")
            parts.append(self.current_diff)
            parts.append("")

        # Test Results (critical for task completion judgment)
        if self.test_results:
            parts.append("## Latest Test/Verification Results")
            if self.verification_success is True:
                parts.append("✅ **Tests Passed**")
            elif self.verification_success is False:
                parts.append("❌ **Tests Failed**")
            else:
                parts.append("⚠️ **Test Status Unknown**")
            parts.append("")
            parts.append(self.test_results)
            parts.append("")
            parts.append(
                "**Important**: If tests pass and task goal is achieved, please set stop_reason='done'"
            )
            parts.append("")

        # Memory Summary
        if self.memory_summary:
            parts.append("## Memory Summary")
            parts.append(self.memory_summary)
            parts.append("")

        result = "\n".join(parts)

        # Truncate if too large
        if len(result.encode("utf-8")) > max_size:
            result = result[:max_size]
            result += "\n\n[Context truncated...]"

        return result


class ContextPackBuilder:
    """Builder for context packs."""

    def __init__(
        self,
        indexer: WorkspaceIndexer,
        project_profile: ProjectProfile,
    ):
        """
        Initialize context pack builder.

        Args:
            indexer: Workspace indexer
            project_profile: Project profile
        """
        self.indexer = indexer
        self.project_profile = project_profile

    def build(
        self,
        goal: str,
        constraints: List[str],
        recent_error: Optional[str] = None,
        current_diff: Optional[str] = None,
        test_results: Optional[str] = None,
        verification_success: Optional[bool] = None,
        memory_summary: Optional[str] = None,
        keywords: Optional[List[str]] = None,
    ) -> ContextPack:
        """
        Build context pack.

        Args:
            goal: Task goal
            constraints: Task constraints
            recent_error: Recent error message
            current_diff: Current diff (from file snapshots)
            memory_summary: Memory summary
            keywords: Keywords for search

        Returns:
            ContextPack instance
        """
        # Build project profile string
        profile_dict = self.project_profile.to_dict()
        profile_str = f"Language: {profile_dict.get('language', 'Unknown')}\n"
        profile_str += f"Package Manager: {profile_dict.get('package_manager', 'Unknown')}\n"
        if profile_dict.get("test_commands"):
            profile_str += (
                f"Test Command Candidates: {', '.join(profile_dict['test_commands'][:3])}\n"
            )

        # Search for relevant files
        relevant_files_str = "None"
        if keywords:
            # Search using keywords
            # Use shorter timeout to avoid blocking
            all_results = []
            for keyword in keywords[:5]:  # Limit to 5 keywords
                try:
                    # Use shorter timeout for search to avoid blocking
                    result = self.indexer.search(keyword, max_results=10)
                    if result.ok and result.stdout:
                        all_results.append(result.stdout)
                except Exception:
                    # If search fails, continue with other keywords
                    continue

            if all_results:
                # Extract file paths from search results
                file_paths = self._extract_file_paths(all_results)
                # Read snippets
                snippets = self.indexer.read_snippets(
                    file_paths[:12],  # Max 12 snippets
                    context_lines=80,
                    max_total_size=80 * 1024,  # 80KB
                    max_file_lines=300,
                )

                if snippets:
                    relevant_files_str = self._format_snippets(snippets)

        # Format recent error
        # CRITICAL: Increase limit to preserve more tool execution information
        # Tool outputs (especially stderr) are critical for LLM decision-making
        # For file viewing commands, preserve even more to show complete file content
        recent_error_str = recent_error or "None"
        # Check if this contains file viewing command output
        max_recent_error = (
            RECENT_ERROR_LIMIT_FILE_CONTENT
            if is_file_content(recent_error_str)
            else RECENT_ERROR_LIMIT_NORMAL
        )
        if len(recent_error_str) > max_recent_error:
            # Show both beginning and end for better context
            recent_error_str = (
                recent_error_str[: max_recent_error // 2]
                + f"\n\n[Omitted {len(recent_error_str) - max_recent_error} chars in middle]...\n\n"
                + recent_error_str[-max_recent_error // 2 :]
                + "\n[Error message truncated, see memory summary for full details]"
            )

        # Format current diff
        current_diff_str = current_diff or "No changes"
        if len(current_diff_str) > DIFF_LIMIT:
            current_diff_str = current_diff_str[:DIFF_LIMIT] + "\n[Diff truncated...]"

        # Format test results
        test_results_str = test_results or None
        if test_results_str and len(test_results_str) > TEST_RESULTS_LIMIT_CONTEXT:
            test_results_str = (
                test_results_str[:TEST_RESULTS_LIMIT_CONTEXT] + "\n[Test results truncated...]"
            )

        return ContextPack(
            goal=goal,
            constraints=constraints,
            project_profile=profile_str,
            relevant_files=relevant_files_str,
            recent_error=recent_error_str,
            current_diff=current_diff_str,
            test_results=test_results_str,
            verification_success=verification_success,
            memory_summary=memory_summary,
        )

    def _extract_file_paths(self, search_results: List[str]) -> List[str]:
        """
        Extract file paths from search results.

        Args:
            search_results: List of search result strings

        Returns:
            List of file paths
        """
        file_paths = set()
        for result in search_results:
            for line in result.splitlines():
                # Grep format: path:line:content
                if ":" in line:
                    path = line.split(":")[0]
                    if path and not path.startswith("Binary"):
                        file_paths.add(path)

        return list(file_paths)[:20]  # Limit to 20 files

    def _format_snippets(self, snippets: List[Dict[str, Any]]) -> str:
        """
        Format file snippets.

        Args:
            snippets: List of snippet dictionaries

        Returns:
            Formatted string
        """
        parts = []
        for snippet in snippets:
            parts.append(f"### {snippet['path']}")
            parts.append("```")
            parts.append(snippet["content"])
            parts.append("```")
            parts.append("")

        return "\n".join(parts)
