"""Batch state manager for reducing disk I/O during phase execution."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atloop.orchestrator.state.manager import StateManager

logger = logging.getLogger(__name__)


class BatchStateManagerMixin:
    """
    Mixin for StateManager to add batch save capability.

    Reduces disk I/O by batching multiple state updates and writing them
    together when appropriate (e.g., at phase boundaries).
    """

    def __init__(self, *args, **kwargs):
        """Initialize batch state manager."""
        super().__init__(*args, **kwargs)
        self._dirty = False
        self._pending_writes = 0
        self._write_threshold = 5  # Batch up to 5 writes before forcing flush

    def mark_dirty(self) -> None:
        """
        Mark state as dirty (needs to be saved).

        The actual save may be deferred until the threshold is reached.
        """
        self._dirty = True
        self._pending_writes += 1

        # Force flush at threshold to prevent too much data loss
        if self._pending_writes >= self._write_threshold:
            logger.debug(
                f"[BatchStateManager] Write threshold ({self._write_threshold}) reached, flushing"
            )
            self.flush()

    def flush(self) -> None:
        """
        Force write state to disk immediately.

        This should be called at phase boundaries or when threshold is reached.
        """
        if self._dirty:
            # Call the original save method from StateManager
            super().save()
            self._dirty = False
            self._pending_writes = 0
            logger.debug("[BatchStateManager] State flushed to disk")

    def save(self, force: bool = False) -> None:
        """
        Save state (with optional batching).

        Args:
            force: If True, force immediate write to disk. Otherwise, may batch.
        """
        if force:
            self.flush()
        else:
            self.mark_dirty()

    def save_on_phase_end(self) -> None:
        """
        Called at the end of each phase to ensure state is persisted.

        This should be called by the workflow after each phase completes.
        """
        self.flush()
        logger.debug("[BatchStateManager] Phase end, state saved")
