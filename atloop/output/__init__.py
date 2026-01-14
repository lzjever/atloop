"""Output system for atloop - event-driven architecture for pluggable output handlers."""

# Import events (always available)
# Import emitter and handler (now available)
from atloop.output.emitter import OutputEventEmitter
from atloop.output.events import (
    BudgetUpdateEvent,
    ErrorEvent,
    EventType,
    LLMCallEvent,
    LLMResultEvent,
    LLMStreamEvent,
    OutputEvent,
    PhaseTransitionEvent,
    TaskCompleteEvent,
    TaskStartEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from atloop.output.handler import OutputHandler

__all__ = [
    "EventType",
    "OutputEvent",
    "TaskStartEvent",
    "PhaseTransitionEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "LLMCallEvent",
    "LLMStreamEvent",
    "LLMResultEvent",
    "BudgetUpdateEvent",
    "TaskCompleteEvent",
    "ErrorEvent",
    "OutputEventEmitter",
    "OutputHandler",
]
