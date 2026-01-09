"""Unified state manager."""

import json
import logging
from pathlib import Path
from typing import Optional

from atloop.memory.state import AgentState
from atloop.orchestrator.job_state import JobState

logger = logging.getLogger(__name__)


class StateManager:
    """Unified state manager - single source of truth."""

    def __init__(self, state_file: Path, job_state: JobState):
        """Initialize state manager.

        Args:
            state_file: Path to state persistence file
            job_state: JobState instance for shared data
        """
        self._state_file = state_file
        self._job_state = job_state
        self._agent_state: Optional[AgentState] = None

    @property
    def agent_state(self) -> AgentState:
        """Get current agent state."""
        if self._agent_state is None:
            raise RuntimeError("State not initialized. Call load() first.")
        return self._agent_state

    def load(self) -> None:
        """Load state from file or create new."""
        if self._state_file.exists():
            try:
                with open(self._state_file, encoding="utf-8") as f:
                    state_dict = json.load(f)
                self._agent_state = AgentState.from_dict(state_dict)
                self._sync()
                logger.info(
                    f"[StateManager] Loaded state: step={self._agent_state.step}, "
                    f"created_files={len(self._agent_state.memory.created_files)}"
                )
                logger.debug(f"[StateManager] State file: {self._state_file}")
            except Exception as e:
                logger.warning(f"[StateManager] Load failed: {e}, creating new state")
                logger.debug(f"[StateManager] Exception details: {type(e).__name__}: {e}")
                self._agent_state = AgentState()
                self._sync()
                self.save()
        else:
            logger.debug(
                f"[StateManager] State file not found: {self._state_file}, creating new state"
            )
            self._agent_state = AgentState()
            self._sync()
            self.save()

    def save(self) -> None:
        """Save state to file."""
        self._sync()
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(self._agent_state.to_dict(), f, indent=2, ensure_ascii=False)
            logger.debug(f"[StateManager] Saved state to: {self._state_file}")
        except Exception as e:
            logger.warning(f"[StateManager] Save failed: {e}")
            logger.debug(f"[StateManager] Exception details: {type(e).__name__}: {e}")

    def update(self, **kwargs) -> None:
        """Update state fields and auto-save."""
        logger.debug(f"[StateManager] Updating state fields: {list(kwargs.keys())}")
        for key, value in kwargs.items():
            if not hasattr(self._agent_state, key):
                raise ValueError(f"Invalid state field: {key}")
            old_value = getattr(self._agent_state, key)
            setattr(self._agent_state, key, value)
            logger.debug(f"[StateManager] Updated {key}: {old_value} -> {value}")
        self.save()

    def _sync(self) -> None:
        """Sync to job_state."""
        if self._agent_state:
            self._job_state.shared_data["agent_state"] = self._agent_state.to_dict()
            self._job_state.update_timestamp()
            logger.debug("[StateManager] Synced to job_state")
