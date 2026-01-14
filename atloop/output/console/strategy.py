"""Formatter strategies for different output formats.

Strategies orchestrate formatting by composing components.
Each strategy selects which components to use and coordinates their execution.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Union
from rich.console import Console, RenderableType

from atloop.output.console.context import FormatterContext
from atloop.output.console.components.base import FormattingComponent
from atloop.output.events import OutputEvent, LLMStreamEvent


class FormatterStrategy(ABC):
    """Abstract formatter strategy.
    
    Strategies orchestrate formatting by composing components.
    Each strategy selects which components to use and coordinates their execution.
    """

    def __init__(self, console: Console, context: FormatterContext):
        """
        Initialize formatter strategy.
        
        Args:
            console: Rich Console instance
            context: Formatter context for state management
        """
        self.console = console
        self.context = context
        self.components: List[FormattingComponent] = []
        self._setup_components()

    @abstractmethod
    def _setup_components(self) -> None:
        """Setup formatting components for this strategy.
        
        Subclasses should override this to add components to self.components.
        """
        pass

    def format(self, event: OutputEvent) -> Optional[Union[RenderableType, str]]:
        """Format event using strategy's components.
        
        Args:
            event: Event to format
        
        Returns:
            Formatted output (Rich renderable or string) or None to skip
        """
        # Update context first
        self.context.update_from_event(event)

        # Try each component
        for component in self.components:
            if component.can_format(self.context, event):
                output = component.format(self.context, event)
                if output is not None:
                    return output

        return None


class MinimalStrategy(FormatterStrategy):
    """Minimal output strategy - essential information only.
    
    Components:
    - HeaderComponent: Task start header
    - FooterComponent: Task completion footer
    - PlanEntryComponent: Current plan entry with position
    - ErrorComponent: Error information (only failures)
    """

    def _setup_components(self) -> None:
        """Setup components for minimal mode."""
        from atloop.output.console.components.header import HeaderComponent
        from atloop.output.console.components.footer import FooterComponent
        from atloop.output.console.components.plan_entry import PlanEntryComponent
        from atloop.output.console.components.error import ErrorComponent

        self.components = [
            HeaderComponent(self.console),
            FooterComponent(self.console),
            PlanEntryComponent(self.console),
            ErrorComponent(self.console),
        ]


class VerboseStrategy(FormatterStrategy):
    """Verbose output strategy - detailed information with tables.
    
    Components:
    - HeaderComponent: Task start header
    - FooterComponent: Task completion footer
    - PlanTableComponent: PLAN phase table with plan information
    - ActionTableComponent: Per-action tables for ACT phase
    - PhaseComponent: Phase transitions
    - ErrorComponent: Error information
    """

    def _setup_components(self) -> None:
        """Setup components for verbose mode."""
        from atloop.output.console.components.header import HeaderComponent
        from atloop.output.console.components.footer import FooterComponent
        from atloop.output.console.components.plan_table import PlanTableComponent
        from atloop.output.console.components.action_table import ActionTableComponent
        from atloop.output.console.components.phase import PhaseComponent
        from atloop.output.console.components.error import ErrorComponent

        self.components = [
            HeaderComponent(self.console),
            FooterComponent(self.console),
            PlanTableComponent(self.console),
            ActionTableComponent(self.console),
            PhaseComponent(self.console),
            ErrorComponent(self.console),
        ]


class DebugStrategy(FormatterStrategy):
    """Debug output strategy - raw output with memory dumps.
    
    Components:
    - RawEventComponent: Raw event output (plain strings)
    - MemoryDumpComponent: Memory information after phase transitions
    - FooterComponent: Task completion footer (plain text format)
    
    Special handling:
    - LLMStreamEvent: Output directly without formatting
    - PhaseTransitionEvent: Output both raw event and memory dump
    - TaskCompleteEvent: Output raw event and footer (plain text)
    """

    def _setup_components(self) -> None:
        """Setup components for debug mode."""
        from atloop.output.console.components.raw_event import RawEventComponent
        from atloop.output.console.components.memory_dump import MemoryDumpComponent
        from atloop.output.console.components.footer import FooterComponent

        self.raw_event_component = RawEventComponent(self.console)
        self.memory_dump_component = MemoryDumpComponent(self.console)
        self.footer_component = FooterComponent(self.console)
        
        self.components = [
            self.raw_event_component,
            self.memory_dump_component,
            self.footer_component,
        ]

    def format(self, event: OutputEvent) -> Optional[Union[RenderableType, str]]:
        """Format event for debug mode.
        
        Special handling for LLMStreamEvent: output directly.
        Special handling for PhaseTransitionEvent: output both raw event and memory dump.
        
        Args:
            event: Event to format
        
        Returns:
            Plain string or None to skip
        """
        # Special handling for LLM streaming - output directly
        if isinstance(event, LLMStreamEvent):
            if event.chunk:
                # Return chunk as-is for direct output
                return event.chunk
            return None
        
        # Special handling for phase transitions - output both raw event and memory dump
        from atloop.output.events import PhaseTransitionEvent, TaskCompleteEvent
        if isinstance(event, PhaseTransitionEvent):
            # Update context first
            self.context.update_from_event(event)
            
            # Get raw event output
            raw_output = self.raw_event_component.format(self.context, event)
            
            # Get memory dump output
            memory_output = self.memory_dump_component.format(self.context, event)
            
            # Combine both outputs
            if raw_output and memory_output:
                return f"{raw_output}\n{memory_output}"
            elif raw_output:
                return raw_output
            elif memory_output:
                return memory_output
            return None
        
        # Special handling for task completion - output raw event and footer (plain text)
        if isinstance(event, TaskCompleteEvent):
            # Update context first
            self.context.update_from_event(event)
            
            # Get raw event output
            raw_output = self.raw_event_component.format(self.context, event)
            
            # Get footer output and convert Rich Text to plain string for debug mode
            footer_output = self.footer_component.format(self.context, event)
            footer_text = ""
            if footer_output:
                # Convert Rich Text to plain string using console's export_text
                from io import StringIO
                buffer = StringIO()
                temp_console = Console(file=buffer, force_terminal=False, legacy_windows=False)
                temp_console.print(footer_output, end="")
                footer_text = buffer.getvalue()
            
            # Combine outputs
            if raw_output and footer_text:
                return f"{raw_output}\n{footer_text}"
            elif raw_output:
                return raw_output
            elif footer_text:
                return footer_text
            return None
        
        # For other events, use normal formatting (first component that returns output)
        return super().format(event)
