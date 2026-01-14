"""Test OutputEventEmitter."""

import threading

from atloop.output.emitter import OutputEventEmitter
from atloop.output.events import EventType, TaskStartEvent


class TestSingleton:
    """Test singleton pattern."""

    def test_singleton(self):
        """Test that only one instance exists."""
        emitter1 = OutputEventEmitter()
        emitter2 = OutputEventEmitter()
        assert emitter1 is emitter2, "Should be singleton"


class TestSubscribeUnsubscribe:
    """Test subscribe/unsubscribe functionality."""

    def test_subscribe(self):
        """Test subscribing a handler."""
        emitter = OutputEventEmitter()
        emitter.clear()

        events_received = []

        def handler(event):
            events_received.append(event)

        emitter.subscribe(handler)
        assert emitter.get_handler_count() == 1

    def test_unsubscribe(self):
        """Test unsubscribing a handler."""
        emitter = OutputEventEmitter()
        emitter.clear()

        def handler(event):
            pass

        emitter.subscribe(handler)
        assert emitter.get_handler_count() == 1

        emitter.unsubscribe(handler)
        assert emitter.get_handler_count() == 0

    def test_multiple_handlers(self):
        """Test multiple handlers."""
        emitter = OutputEventEmitter()
        emitter.clear()

        events1 = []
        events2 = []

        def handler1(event):
            events1.append(event)

        def handler2(event):
            events2.append(event)

        emitter.subscribe(handler1)
        emitter.subscribe(handler2)
        assert emitter.get_handler_count() == 2

        event = TaskStartEvent(
            step=1,
            task_id="test",
            goal="test",
            workspace_root="/tmp",
            model="test",
        )
        emitter.emit(event)

        assert len(events1) == 1
        assert len(events2) == 1

    def test_duplicate_subscribe(self):
        """Test that duplicate subscriptions are ignored."""
        emitter = OutputEventEmitter()
        emitter.clear()

        def handler(event):
            pass

        emitter.subscribe(handler)
        emitter.subscribe(handler)  # Duplicate
        assert emitter.get_handler_count() == 1


class TestEmit:
    """Test event emission."""

    def test_emit_to_handler(self):
        """Test emitting event to handler."""
        emitter = OutputEventEmitter()
        emitter.clear()

        events_received = []

        def handler(event):
            events_received.append(event)

        emitter.subscribe(handler)

        event = TaskStartEvent(
            step=1,
            task_id="test",
            goal="test",
            workspace_root="/tmp",
            model="test",
        )
        emitter.emit(event)

        assert len(events_received) == 1
        assert events_received[0].event_type == EventType.TASK_START
        assert events_received[0].step == 1

    def test_emit_no_handlers(self):
        """Test emitting when no handlers are subscribed."""
        emitter = OutputEventEmitter()
        emitter.clear()

        event = TaskStartEvent(
            step=1,
            task_id="test",
            goal="test",
            workspace_root="/tmp",
            model="test",
        )
        # Should not raise exception
        emitter.emit(event)

    def test_handler_error_does_not_crash(self):
        """Test that handler errors don't crash emitter."""
        emitter = OutputEventEmitter()
        emitter.clear()

        def failing_handler(event):
            raise ValueError("Handler error")

        emitter.subscribe(failing_handler)

        event = TaskStartEvent(
            step=1,
            task_id="test",
            goal="test",
            workspace_root="/tmp",
            model="test",
        )
        # Should not raise exception
        emitter.emit(event)


class TestThreadSafety:
    """Test thread safety."""

    def test_concurrent_subscribe(self):
        """Test concurrent subscriptions."""
        emitter = OutputEventEmitter()
        emitter.clear()

        def handler(event):
            pass

        def subscribe_thread():
            for _ in range(100):
                emitter.subscribe(handler)

        threads = [threading.Thread(target=subscribe_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have exactly 1 handler (duplicates ignored)
        assert emitter.get_handler_count() == 1

    def test_concurrent_emit(self):
        """Test concurrent emissions."""
        emitter = OutputEventEmitter()
        emitter.clear()

        events_received = []
        lock = threading.Lock()

        def handler(event):
            with lock:
                events_received.append(event)

        emitter.subscribe(handler)

        def emit_thread():
            for i in range(10):
                event = TaskStartEvent(
                    step=i,
                    task_id="test",
                    goal="test",
                    workspace_root="/tmp",
                    model="test",
                )
                emitter.emit(event)

        threads = [threading.Thread(target=emit_thread) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should receive 100 events (10 threads * 10 events)
        assert len(events_received) == 100


class TestClear:
    """Test clear functionality."""

    def test_clear_handlers(self):
        """Test clearing all handlers."""
        emitter = OutputEventEmitter()
        emitter.clear()

        def handler(event):
            pass

        emitter.subscribe(handler)
        assert emitter.get_handler_count() == 1

        emitter.clear()
        assert emitter.get_handler_count() == 0
