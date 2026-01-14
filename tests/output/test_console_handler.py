"""Test console output handler and formatters."""

from io import StringIO

from rich.console import Console

from atloop.output.console.formatters import (
    MinimalConsoleFormatter,
    VerboseConsoleFormatter,
)
from atloop.output.console.handler import ConsoleOutputHandler
from atloop.output.events import (
    BudgetUpdateEvent,
    ErrorEvent,
    LLMCallEvent,
    LLMResultEvent,
    LLMStreamEvent,
    PhaseTransitionEvent,
    TaskCompleteEvent,
    TaskStartEvent,
    ToolCallEvent,
    ToolResultEvent,
)


class TestMinimalConsoleFormatter:
    """Test minimal console formatter."""

    def test_format_task_start(self):
        """Test formatting TaskStartEvent."""
        console = Console(file=StringIO())
        formatter = MinimalConsoleFormatter(console)

        event = TaskStartEvent(
            step=0,
            task_id="test",
            goal="Fix bug",
            workspace_root="/tmp",
            model="test",
            budget={"max_llm_calls": 50},
        )
        output = formatter.format(event)
        assert output is not None
        # Check it's a Rich renderable (Panel)
        from rich.panel import Panel

        assert isinstance(output, Panel)

    def test_format_phase_transition(self):
        """Test formatting PhaseTransitionEvent."""
        console = Console(file=StringIO())
        formatter = MinimalConsoleFormatter(console)

        event = PhaseTransitionEvent(
            step=1,
            task_id="test",
            phase="DISCOVER",
        )
        output = formatter.format(event)
        assert output is not None
        assert "DISCOVER" in str(output)
        assert "[STEP 1]" in str(output)

    def test_format_tool_failure(self):
        """Test formatting ToolResultEvent (failure only)."""
        console = Console(file=StringIO())
        formatter = MinimalConsoleFormatter(console)

        # Failure should be shown
        event = ToolResultEvent(
            step=3,
            task_id="test",
            tool_name="run",
            success=False,
            error="Command failed",
        )
        output = formatter.format(event)
        assert output is not None
        assert "failed" in str(output).lower()

        # Success should be skipped in minimal mode
        event = ToolResultEvent(
            step=3,
            task_id="test",
            tool_name="run",
            success=True,
        )
        output = formatter.format(event)
        assert output is None

    def test_format_task_complete(self):
        """Test formatting TaskCompleteEvent."""
        console = Console(file=StringIO())
        formatter = MinimalConsoleFormatter(console)

        event = TaskCompleteEvent(
            step=10,
            task_id="test",
            status="success",
            final_step=10,
            duration_sec=120,
            budget_used={"llm_calls": 12, "tool_calls": 8},
        )
        output = formatter.format(event)
        assert output is not None
        # Render to check it's a valid Rich renderable
        console.print(output, end="")
        # Just check that output exists and is not None
        assert output is not None

    def test_format_error(self):
        """Test formatting ErrorEvent."""
        console = Console(file=StringIO())
        formatter = MinimalConsoleFormatter(console)

        event = ErrorEvent(
            step=5,
            task_id="test",
            phase="ACT",
            error_type="ValueError",
            error_message="Test error",
        )
        output = formatter.format(event)
        assert output is not None
        # Render to check it's a valid Rich renderable
        console.print(output, end="")
        # Just check that output exists and is not None
        assert output is not None

    def test_skip_other_events(self):
        """Test that other events are skipped in minimal mode."""
        console = Console(file=StringIO())
        formatter = MinimalConsoleFormatter(console)

        # ToolCallEvent should be skipped
        event = ToolCallEvent(
            step=3,
            task_id="test",
            tool_name="run",
            tool_args={"cmd": "test"},
        )
        output = formatter.format(event)
        assert output is None

        # LLMCallEvent should be skipped
        event = LLMCallEvent(
            step=2,
            task_id="test",
            model="test",
            prompt_length=100,
        )
        output = formatter.format(event)
        assert output is None


class TestVerboseConsoleFormatter:
    """Test verbose console formatter."""

    def test_format_all_events(self):
        """Test that verbose formatter handles all event types."""
        console = Console(file=StringIO())
        formatter = VerboseConsoleFormatter(console)

        # TaskStartEvent
        event = TaskStartEvent(
            step=0,
            task_id="test",
            goal="Fix bug",
            workspace_root="/tmp",
            model="test",
            budget={"max_llm_calls": 50},
        )
        output = formatter.format(event)
        assert output is not None

        # PhaseTransitionEvent
        event = PhaseTransitionEvent(
            step=1,
            task_id="test",
            phase="DISCOVER",
        )
        output = formatter.format(event)
        assert output is not None

        # ToolCallEvent
        event = ToolCallEvent(
            step=3,
            task_id="test",
            tool_name="run",
            tool_args={"cmd": "test"},
        )
        output = formatter.format(event)
        assert output is not None

        # ToolResultEvent (both success and failure)
        event = ToolResultEvent(
            step=3,
            task_id="test",
            tool_name="run",
            success=True,
            stdout="output",
        )
        output = formatter.format(event)
        assert output is not None

        # LLMCallEvent
        event = LLMCallEvent(
            step=2,
            task_id="test",
            model="test",
            prompt_length=100,
        )
        output = formatter.format(event)
        assert output is not None

        # LLMResultEvent
        event = LLMResultEvent(
            step=2,
            task_id="test",
            model="test",
            tokens_in=100,
            tokens_out=50,
            actions=[],
            stop_reason="continue",
            duration_ms=1000,
        )
        output = formatter.format(event)
        assert output is not None

        # BudgetUpdateEvent
        event = BudgetUpdateEvent(
            step=5,
            task_id="test",
            llm_calls_used=10,
            llm_calls_max=50,
            tool_calls_used=5,
            tool_calls_max=100,
            wall_time_sec_used=30,
            wall_time_sec_max=300,
        )
        output = formatter.format(event)
        assert output is not None

        # TaskCompleteEvent
        event = TaskCompleteEvent(
            step=10,
            task_id="test",
            status="success",
            final_step=10,
            duration_sec=120,
            budget_used={"llm_calls": 12},
        )
        output = formatter.format(event)
        assert output is not None

        # ErrorEvent
        event = ErrorEvent(
            step=5,
            task_id="test",
            phase="ACT",
            error_type="ValueError",
            error_message="Test error",
        )
        output = formatter.format(event)
        assert output is not None

    def test_llm_stream_accumulation(self):
        """Test LLM stream event accumulation."""
        console = Console(file=StringIO())
        formatter = VerboseConsoleFormatter(console)

        # Stream chunks
        event1 = LLMStreamEvent(
            step=2,
            task_id="test",
            chunk="Hello ",
            is_complete=False,
        )
        output1 = formatter.format(event1)
        assert output1 is None  # Chunks are accumulated, not printed

        event2 = LLMStreamEvent(
            step=2,
            task_id="test",
            chunk="World",
            is_complete=False,
        )
        output2 = formatter.format(event2)
        assert output2 is None

        # Complete stream
        event3 = LLMStreamEvent(
            step=2,
            task_id="test",
            chunk="",
            is_complete=True,
        )
        output3 = formatter.format(event3)
        assert output3 is None  # Completion clears buffer


class TestConsoleOutputHandler:
    """Test console output handler."""

    def test_handler_initialization(self):
        """Test handler initialization."""
        console = Console(file=StringIO())
        handler = ConsoleOutputHandler(verbose=False, enabled=True, console=console)
        assert handler.is_enabled() is True
        assert handler.verbose is False
        assert isinstance(handler.formatter, MinimalConsoleFormatter)

        handler = ConsoleOutputHandler(verbose=True, enabled=True, console=console)
        assert handler.verbose is True
        assert isinstance(handler.formatter, VerboseConsoleFormatter)

    def test_handler_enable_disable(self):
        """Test handler enable/disable."""
        console = Console(file=StringIO())
        handler = ConsoleOutputHandler(enabled=True, console=console)

        event = TaskStartEvent(
            step=0,
            task_id="test",
            goal="test",
            workspace_root="/tmp",
            model="test",
        )

        # Enabled handler should process events
        handler.handle(event)  # Should not raise

        # Disabled handler should ignore events
        handler.enabled = False
        handler.handle(event)  # Should not raise and should not output

    def test_handler_error_handling(self):
        """Test that handler errors don't crash."""
        console = Console(file=StringIO())

        class FailingFormatter(MinimalConsoleFormatter):
            def format(self, event):
                raise ValueError("Formatter error")

        handler = ConsoleOutputHandler(verbose=False, enabled=True, console=console)
        handler.formatter = FailingFormatter(console)

        event = TaskStartEvent(
            step=0,
            task_id="test",
            goal="test",
            workspace_root="/tmp",
            model="test",
        )

        # Should not raise exception
        handler.handle(event)
