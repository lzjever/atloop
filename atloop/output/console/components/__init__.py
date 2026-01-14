"""Formatting components for console output.

This package contains reusable formatting components that can be composed
by formatter strategies to create different output formats.
"""

from atloop.output.console.components.base import FormattingComponent
from atloop.output.console.components.header import HeaderComponent
from atloop.output.console.components.footer import FooterComponent
from atloop.output.console.components.plan_entry import PlanEntryComponent
from atloop.output.console.components.plan_table import PlanTableComponent
from atloop.output.console.components.action_table import ActionTableComponent
from atloop.output.console.components.diff import DiffComponent
from atloop.output.console.components.error import ErrorComponent
from atloop.output.console.components.phase import PhaseComponent
from atloop.output.console.components.raw_event import RawEventComponent
from atloop.output.console.components.memory_dump import MemoryDumpComponent

__all__ = [
    "FormattingComponent",
    "HeaderComponent",
    "FooterComponent",
    "PlanEntryComponent",
    "PlanTableComponent",
    "ActionTableComponent",
    "DiffComponent",
    "ErrorComponent",
    "PhaseComponent",
    "RawEventComponent",
    "MemoryDumpComponent",
]
