"""Event definitions for output system.

All events are immutable dataclasses that represent state changes in the orchestrator.
Handlers subscribe to these events and format/display them appropriately.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from datetime import datetime
from enum import Enum


class EventType(Enum):
    """Event type enumeration."""

    TASK_START = "task_start"
    PHASE_TRANSITION = "phase_transition"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    LLM_CALL = "llm_call"
    LLM_STREAM = "llm_stream"
    LLM_RESULT = "llm_result"
    BUDGET_UPDATE = "budget_update"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"


@dataclass(frozen=True)
class OutputEvent:
    """Base class for all output events.

    All events are immutable (frozen) and must have:
    - event_type: EventType enum
    - timestamp: When event occurred
    - step: Current step number
    - task_id: Task identifier
    """

    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    step: int = 0
    task_id: str = ""


@dataclass(frozen=True)
class TaskStartEvent(OutputEvent):
    """Event emitted when task starts."""

    event_type: EventType = field(default=EventType.TASK_START)
    goal: str = ""
    workspace_root: str = ""
    model: str = ""
    budget: Dict[str, int] = field(default_factory=dict)  # {"max_llm_calls": 50, ...}
    session_id: Optional[str] = None  # Agent session ID for resuming/continuing runs
    runs_dir: str = ""  # Full path to runs/{task_id}/ directory
    start_time: datetime = field(default_factory=datetime.now)  # Task start timestamp


@dataclass(frozen=True)
class PhaseTransitionEvent(OutputEvent):
    """Event emitted on phase transitions."""

    event_type: EventType = field(default=EventType.PHASE_TRANSITION)
    phase: str = ""  # "DISCOVER", "PLAN", "ACT", "VERIFY"
    previous_phase: Optional[str] = None
    details: Optional[Dict[str, Any]] = field(default_factory=dict)
    plan_snapshot: Optional[List[Any]] = None  # Optional plan snapshot for minimal mode display


@dataclass(frozen=True)
class ToolCallEvent(OutputEvent):
    """Event emitted before tool execution."""

    event_type: EventType = field(default=EventType.TOOL_CALL)
    tool_name: str = ""
    tool_args: Dict[str, Any] = field(default_factory=dict)
    tool_id: Optional[str] = None  # For tracking async operations


@dataclass(frozen=True)
class ToolResultEvent(OutputEvent):
    """Event emitted after tool execution."""

    event_type: EventType = field(default=EventType.TOOL_RESULT)
    tool_name: str = ""
    tool_id: Optional[str] = None
    success: bool = False
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass(frozen=True)
class LLMCallEvent(OutputEvent):
    """Event emitted before LLM call."""

    event_type: EventType = field(default=EventType.LLM_CALL)
    model: str = ""
    prompt_length: int = 0
    tokens_in: Optional[int] = None


@dataclass(frozen=True)
class LLMStreamEvent(OutputEvent):
    """Event emitted for each LLM stream chunk."""

    event_type: EventType = field(default=EventType.LLM_STREAM)
    chunk: str = ""
    is_complete: bool = False


@dataclass(frozen=True)
class LLMResultEvent(OutputEvent):
    """Event emitted after LLM call completes."""

    event_type: EventType = field(default=EventType.LLM_RESULT)
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    actions: List[Dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    duration_ms: int = 0
    full_response: Optional[str] = None  # Only in verbose mode


@dataclass(frozen=True)
class BudgetUpdateEvent(OutputEvent):
    """Event emitted on budget updates."""

    event_type: EventType = field(default=EventType.BUDGET_UPDATE)
    llm_calls_used: int = 0
    llm_calls_max: int = 0
    tool_calls_used: int = 0
    tool_calls_max: int = 0
    wall_time_sec_used: int = 0
    wall_time_sec_max: int = 0


@dataclass(frozen=True)
class TaskCompleteEvent(OutputEvent):
    """Event emitted when task completes."""

    event_type: EventType = field(default=EventType.TASK_COMPLETE)
    status: str = ""  # "success", "failure", "error"
    final_step: int = 0
    duration_sec: int = 0
    budget_used: Dict[str, int] = field(default_factory=dict)
    files_modified: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    error: Optional[str] = None
    session_id: Optional[str] = None  # Agent session ID
    runs_dir: str = ""  # Full path to runs/{task_id}/ directory
    end_time: datetime = field(default_factory=datetime.now)  # Task end timestamp
    start_time: Optional[datetime] = None  # Task start timestamp (for duration calculation)


@dataclass(frozen=True)
class ErrorEvent(OutputEvent):
    """Event emitted on errors."""

    event_type: EventType = field(default=EventType.ERROR)
    phase: str = ""
    error_type: str = ""
    error_message: str = ""
    error_details: Optional[Dict[str, Any]] = field(default_factory=dict)
    recoverable: bool = False
    recovery_action: Optional[str] = None
