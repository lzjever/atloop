"""Test OutputHandler interface."""

import pytest
from atloop.output.handler import OutputHandler
from atloop.output.events import OutputEvent, TaskStartEvent


class TestAbstractBaseClass:
    """Test that OutputHandler is abstract."""

    def test_cannot_instantiate(self):
        """Test that OutputHandler cannot be instantiated directly."""
        with pytest.raises(TypeError):
            OutputHandler()


class TestConcreteImplementation:
    """Test concrete handler implementation."""

    def test_handler_enabled(self):
        """Test handler enable/disable."""
        class TestHandler(OutputHandler):
            def handle(self, event: OutputEvent) -> None:
                pass

        handler = TestHandler(enabled=True)
        assert handler.is_enabled() is True

        handler = TestHandler(enabled=False)
        assert handler.is_enabled() is False

    def test_handler_handle(self):
        """Test handler handle method."""
        events_received = []

        class TestHandler(OutputHandler):
            def handle(self, event: OutputEvent) -> None:
                if self.enabled:
                    events_received.append(event)

        handler = TestHandler(enabled=True)
        event = TaskStartEvent(
            step=1,
            task_id="test",
            goal="test",
            workspace_root="/tmp",
            model="test",
        )
        handler.handle(event)
        assert len(events_received) == 1

    def test_disabled_handler_ignores_events(self):
        """Test that disabled handler ignores events."""
        events_received = []

        class TestHandler(OutputHandler):
            def handle(self, event: OutputEvent) -> None:
                if self.enabled:
                    events_received.append(event)

        handler = TestHandler(enabled=False)
        event = TaskStartEvent(
            step=1,
            task_id="test",
            goal="test",
            workspace_root="/tmp",
            model="test",
        )
        handler.handle(event)
        assert len(events_received) == 0

    def test_lifecycle_methods(self):
        """Test start/stop lifecycle methods."""
        class LifecycleHandler(OutputHandler):
            def __init__(self):
                super().__init__()
                self.started = False
                self.stopped = False

            def handle(self, event: OutputEvent) -> None:
                pass

            def start(self) -> None:
                self.started = True

            def stop(self) -> None:
                self.stopped = True

        handler = LifecycleHandler()
        handler.start()
        assert handler.started is True

        handler.stop()
        assert handler.stopped is True
