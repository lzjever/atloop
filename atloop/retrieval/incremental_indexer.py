"""Incremental workspace indexer for indexing new/changed files."""

import logging
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from atloop.memory.state import AgentState
    from atloop.retrieval.indexer import WorkspaceIndexer

logger = logging.getLogger(__name__)


class IncrementalIndexer:
    """
    Incremental indexer for workspace files.

    Only indexes files that have been created or modified since the last DISCOVER phase,
    rather than re-indexing the entire workspace. This improves performance for
    iterative task execution.
    """

    def __init__(self, indexer: "WorkspaceIndexer"):
        """
        Initialize incremental indexer.

        Args:
            indexer: The workspace indexer to use for indexing files
        """
        self.indexer = indexer

    def track_changes_since_last_discover(self, state: "AgentState") -> List[str]:
        """
        Get list of files that have changed since the last DISCOVER phase.

        Args:
            state: Current agent state

        Returns:
            List of file paths that have been created or modified
        """
        changed_files = []

        # 1. Check newly created files
        if state.memory.created_files:
            # Get files created in recent steps (last 5 steps worth of files)
            # This ensures we don't re-index files that were already indexed
            recent_created = state.memory.created_files[-20:]  # Last 20 created files
            changed_files.extend(recent_created)
            logger.debug(
                f"[IncrementalIndexer] Found {len(recent_created)} newly created files "
                f"out of {len(state.memory.created_files)} total"
            )

        # 2. Check modified files that might not be in created_files
        # (e.g., files that were edited but existed before)
        if state.memory.modified_files_content:
            current_step = state.step
            for record in state.memory.modified_files_content:
                file_path = record.get("path", "")
                last_modified = record.get("last_modified_step", 0)

                # Only include files modified in the last 3 steps
                # This avoids re-indexing old modifications
                if last_modified >= current_step - 3 and file_path not in changed_files:
                    changed_files.append(file_path)

            logger.debug(
                f"[IncrementalIndexer] Found {len(changed_files)} total changed files "
                f"(including recently modified)"
            )

        return changed_files

    def index_new_files(self, file_paths: List[str]) -> int:
        """
        Incrementally index new files into the workspace indexer.

        Args:
            file_paths: List of file paths to index

        Returns:
            Number of files successfully indexed
        """
        if not file_paths:
            logger.debug("[IncrementalIndexer] No files to index")
            return 0

        indexed_count = 0
        for file_path in file_paths:
            try:
                # Use the workspace indexer's search capability to validate the file exists
                # The indexer will automatically discover files during search
                # For incremental indexing, we just need to ensure the file is discoverable
                result = self.indexer.search(file_path, max_results=1)

                # If search succeeded, the file is indexed
                if result.ok:
                    indexed_count += 1
                    logger.debug(f"[IncrementalIndexer] Indexed file: {file_path}")
                else:
                    logger.warning(
                        f"[IncrementalIndexer] Failed to index file: {file_path}: {result.stderr}"
                    )
            except Exception as e:
                logger.warning(
                    f"[IncrementalIndexer] Exception indexing file {file_path}: {e}"
                )

        logger.info(
            f"[IncrementalIndexer] Incrementally indexed {indexed_count}/{len(file_paths)} files"
        )
        return indexed_count

    def extract_keywords_from_files(self, file_paths: List[str]) -> List[str]:
        """
        Extract keywords from file paths for context building.

        Args:
            file_paths: List of file paths to extract keywords from

        Returns:
            List of keywords extracted from file paths
        """
        keywords = []

        for file_path in file_paths:
            # Extract filename without extension
            import os

            filename = os.path.basename(file_path)
            name_without_ext = os.path.splitext(filename)[0]

            # Add filename as keyword
            if name_without_ext:
                keywords.append(name_without_ext)

            # Extract parts of camelCase or snake_case names
            # snake_case: split by underscore
            if "_" in name_without_ext:
                parts = name_without_ext.split("_")
                keywords.extend([p for p in parts if len(p) > 2])

            # camelCase: split by capital letters
            import re

            camel_parts = re.findall(r'[A-Z][a-z]+', name_without_ext)
            keywords.extend(camel_parts)

            # Add file extension as keyword
            _, ext = os.path.splitext(file_path)
            if ext:
                # Remove the dot and add as keyword
                keywords.append(ext[1:])

        # Remove duplicates and limit
        unique_keywords = list(set(keywords))
        return unique_keywords[:20]  # Limit to 20 keywords
