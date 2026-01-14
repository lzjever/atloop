"""Event emitter for output system.

Thread-safe singleton that emits events to subscribed handlers.
Core orchestrator emits events here, handlers subscribe to receive them.
"""

import logging
from typing import List, Callable, Optional
from threading import Lock

from atloop.output.events import OutputEvent

logger = logging.getLogger(__name__)


class OutputEventEmitter:
    """
    Singleton event emitter for output events.

    Thread-safe implementation using observer pattern.
    Core orchestrator emits events here, handlers subscribe.
    """

    _instance: Optional["OutputEventEmitter"] = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._handlers: List[Callable[[OutputEvent], None]] = []
        self._handler_lock = Lock()
        self._initialized = True

    def subscribe(self, handler: Callable[[OutputEvent], None]) -> None:
        """
        Subscribe a handler to receive all events.

        Args:
            handler: Callable that takes an OutputEvent and returns None
        """
        with self._handler_lock:
            if handler not in self._handlers:
                self._handlers.append(handler)
                logger.debug(f"Handler subscribed: {handler.__name__ if hasattr(handler, '__name__') else type(handler).__name__}")

    def unsubscribe(self, handler: Callable[[OutputEvent], None]) -> None:
        """
        Unsubscribe a handler.

        Args:
            handler: Handler to remove
        """
        with self._handler_lock:
            if handler in self._handlers:
                self._handlers.remove(handler)
                logger.debug(f"Handler unsubscribed: {handler.__name__ if hasattr(handler, '__name__') else type(handler).__name__}")

    def emit(self, event: OutputEvent) -> None:
        """
        Emit an event to all subscribed handlers.

        Args:
            event: Event to emit
        """
        with self._handler_lock:
            handlers = list(self._handlers)  # Copy to avoid lock during iteration

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                # Log error but don't crash - output should never break execution
                logger.error(f"Output handler error: {e}", exc_info=True)

    def clear(self) -> None:
        """Clear all handlers (for testing)."""
        with self._handler_lock:
            self._handlers.clear()
            logger.debug("All handlers cleared")

    def get_handler_count(self) -> int:
        """Get number of subscribed handlers (for testing)."""
        with self._handler_lock:
            return len(self._handlers)
