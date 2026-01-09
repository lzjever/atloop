"""Simple JobState implementation to replace routilux dependency."""

import json
from datetime import datetime
from typing import Any, Dict, List


class JobState:
    """Simple job state for tracking execution state.

    This is a minimal replacement for routilux.JobState that provides
    only the functionality needed by the atloop project.
    """

    def __init__(self, flow_id: str = ""):
        """Initialize job state.

        Args:
            flow_id: Flow identifier.
        """
        self.flow_id: str = flow_id
        self.shared_data: Dict[str, Any] = {}
        self.shared_log: List[Dict[str, Any]] = []
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()

    def serialize(self) -> str:
        """Serialize job state to JSON string.

        Returns:
            JSON string representation of the job state.
        """
        data = {
            "flow_id": self.flow_id,
            "shared_data": self.shared_data,
            "shared_log": self.shared_log,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        return json.dumps(data, ensure_ascii=False)

    def deserialize(self, data: str) -> None:
        """Deserialize job state from JSON string.

        Args:
            data: JSON string representation of the job state.
        """
        obj = json.loads(data)
        self.flow_id = obj.get("flow_id", "")
        self.shared_data = obj.get("shared_data", {})
        self.shared_log = obj.get("shared_log", [])
        if "created_at" in obj:
            self.created_at = datetime.fromisoformat(obj["created_at"])
        if "updated_at" in obj:
            self.updated_at = datetime.fromisoformat(obj["updated_at"])

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()
