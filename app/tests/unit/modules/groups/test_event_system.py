"""Unit tests for groups event system.

Tests event registration, synchronous dispatch, background dispatch,
exception handling, and lifecycle management.
"""

import pytest
from threading import Event
from unittest.mock import patch

from modules.groups.events import system as event_system


pytestmark = pytest.mark.unit


class TestEventRegistration:
    """Test event handler registration."""

    def test_register_single_handler(self):
        """Handler decorator registers handler for event type."""
        # Clear handlers
        event_system.EVENT_HANDLERS.clear()

        @event_system.register_event_handler("test.event")
        def handler(payload):
            return "handled"

        assert "test.event" in event_system.EVENT_HANDLERS
        assert handler in event_system.EVENT_HANDLERS["test.event"]

    def test_register_multiple_handlers_same_event(self):
        """Multiple handlers can register for same event type."""
        event_system.EVENT_HANDLERS.clear()

        @event_system.register_event_handler("test.multi")
        def handler1(payload):
            return "h1"

        @event_system.register_event_handler("test.multi")
        def handler2(payload):
            return "h2"

        handlers = event_system.EVENT_HANDLERS["test.multi"]
        assert len(handlers) == 2
        assert handler1 in handlers
        assert handler2 in handlers

    def test_register_handler_returns_original_function(self):
        """Decorator returns original function."""
        event_system.EVENT_HANDLERS.clear()

        def original_handler(payload):
            return payload

        decorated = event_system.register_event_handler("test.return")(original_handler)
        assert decorated is original_handler

    def test_get_registered_events_empty(self):
        """get_registered_events returns empty list when no handlers."""
        event_system.EVENT_HANDLERS.clear()
        assert event_system.get_registered_events() == []

    def test_get_registered_events_with_handlers(self):
        """get_registered_events returns list of event types."""
        event_system.EVENT_HANDLERS.clear()

        @event_system.register_event_handler("event.one")
        def h1(p):
            pass

        @event_system.register_event_handler("event.two")
        def h2(p):
            pass

        events = event_system.get_registered_events()
        assert "event.one" in events
        assert "event.two" in events

    def test_get_handlers_for_event(self):
        """get_handlers_for_event returns handlers for event type."""
        event_system.EVENT_HANDLERS.clear()

        @event_system.register_event_handler("test.get")
        def handler1(p):
            pass

        @event_system.register_event_handler("test.get")
        def handler2(p):
            pass

        handlers = event_system.get_handlers_for_event("test.get")
        assert len(handlers) == 2
        assert handler1 in handlers
        assert handler2 in handlers

    def test_get_handlers_for_unregistered_event(self):
        """get_handlers_for_event returns empty list for unregistered event."""
        event_system.EVENT_HANDLERS.clear()
        assert event_system.get_handlers_for_event("nonexistent") == []


class TestSynchronousDispatch:
    """Test synchronous event dispatch."""

    def test_dispatch_single_handler(self):
        """dispatch_event calls registered handler and returns results."""
        event_system.EVENT_HANDLERS.clear()

        result_payload = {}

        @event_system.register_event_handler("test.sync")
        def handler(payload):
            result_payload.update(payload)
            return "handled"

        results = event_system.dispatch_event("test.sync", {"key": "value"})

        assert results == ["handled"]
        assert result_payload == {"key": "value"}

    def test_dispatch_multiple_handlers(self):
        """dispatch_event calls all handlers and returns all results."""
        event_system.EVENT_HANDLERS.clear()

        @event_system.register_event_handler("test.multiple")
        def handler1(payload):
            return "r1"

        @event_system.register_event_handler("test.multiple")
        def handler2(payload):
            return "r2"

        results = event_system.dispatch_event("test.multiple", {})

        assert len(results) == 2
        assert "r1" in results
        assert "r2" in results

    def test_dispatch_unregistered_event(self):
        """dispatch_event returns empty list for unregistered event."""
        event_system.EVENT_HANDLERS.clear()
        results = event_system.dispatch_event("nonexistent", {})
        assert results == []

    def test_dispatch_passes_payload_to_handler(self):
        """dispatch_event passes payload dict to handler."""
        event_system.EVENT_HANDLERS.clear()

        received_payload = {}

        @event_system.register_event_handler("test.payload")
        def handler(payload):
            received_payload.update(payload)

        test_payload = {"a": 1, "b": "two", "c": [3]}
        event_system.dispatch_event("test.payload", test_payload)

        assert received_payload == test_payload

    def test_dispatch_handler_exception_does_not_stop_others(self):
        """Handler exception is logged but other handlers still run."""
        event_system.EVENT_HANDLERS.clear()
        called = []

        @event_system.register_event_handler("test.exc")
        def bad_handler(payload):
            called.append("bad")
            raise ValueError("handler error")

        @event_system.register_event_handler("test.exc")
        def good_handler(payload):
            called.append("good")
            return "success"

        results = event_system.dispatch_event("test.exc", {})

        assert "bad" in called
        assert "good" in called
        assert "success" in results

    def test_dispatch_handler_exception_logged(self):
        """Handler exception is logged."""
        event_system.EVENT_HANDLERS.clear()

        @event_system.register_event_handler("test.log_exc")
        def failing_handler(payload):
            raise RuntimeError("test error")

        with patch("modules.groups.events.system.logger") as mock_logger:
            event_system.dispatch_event("test.log_exc", {})
            mock_logger.error.assert_called()

    def test_dispatch_handler_receives_correct_payload(self):
        """Handler receives correct payload even if previous handler modified it."""
        event_system.EVENT_HANDLERS.clear()
        payloads = []

        @event_system.register_event_handler("test.payload_order")
        def handler1(payload):
            payloads.append(dict(payload))

        @event_system.register_event_handler("test.payload_order")
        def handler2(payload):
            payloads.append(dict(payload))

        event_system.dispatch_event("test.payload_order", {"x": 1})

        # Both should receive same payload
        assert payloads[0] == {"x": 1}
        assert payloads[1] == {"x": 1}

    def test_dispatch_returns_handler_return_values(self):
        """dispatch_event returns list of handler return values."""
        event_system.EVENT_HANDLERS.clear()

        @event_system.register_event_handler("test.returns")
        def handler1(p):
            return 42

        @event_system.register_event_handler("test.returns")
        def handler2(p):
            return "hello"

        @event_system.register_event_handler("test.returns")
        def handler3(p):
            return None

        results = event_system.dispatch_event("test.returns", {})
        assert results == [42, "hello", None]


class TestBackgroundDispatch:
    """Test background/asynchronous dispatch."""

    def teardown_method(self):
        """Shutdown executor after each test."""
        event_system.shutdown_event_executor(wait=True)
        event_system._executor_shutdown = False
        event_system._EXECUTOR = None
        event_system.EVENT_HANDLERS.clear()

    def test_dispatch_background_runs_handler(self):
        """dispatch_background runs handler in background executor."""
        event_system.EVENT_HANDLERS.clear()
        evt = Event()

        @event_system.register_event_handler("test.bg")
        def bg_handler(payload):
            evt.set()

        event_system.start_event_executor(max_workers=1)
        event_system.dispatch_background("test.bg", {})

        # Wait for background handler to run
        assert evt.wait(2), "background handler did not run in time"

    def test_dispatch_background_passes_payload(self):
        """dispatch_background passes payload to handler."""
        event_system.EVENT_HANDLERS.clear()
        received = {}
        evt = Event()

        @event_system.register_event_handler("test.bg_payload")
        def handler(payload):
            received.update(payload)
            evt.set()

        event_system.start_event_executor(max_workers=1)
        event_system.dispatch_background("test.bg_payload", {"key": "value"})

        evt.wait(2)
        assert received == {"key": "value"}

    def test_dispatch_background_returns_none(self):
        """dispatch_background returns None (fire-and-forget)."""
        event_system.EVENT_HANDLERS.clear()

        @event_system.register_event_handler("test.bg_return")
        def handler(payload):
            return "should_be_ignored"

        event_system.start_event_executor(max_workers=1)
        result = event_system.dispatch_background("test.bg_return", {})

        assert result is None

    def test_dispatch_background_after_shutdown_ignored(self):
        """dispatch_background is no-op after executor shutdown."""
        event_system.EVENT_HANDLERS.clear()
        called = []

        @event_system.register_event_handler("test.post_shutdown")
        def handler(payload):
            called.append(True)

        event_system.shutdown_event_executor(wait=True)

        # Should not raise, just return
        result = event_system.dispatch_background("test.post_shutdown", {})

        assert result is None
        # Give time for any stray thread
        import time

        time.sleep(0.1)
        assert not called

    def test_dispatch_background_multiple_handlers(self):
        """dispatch_background calls all registered handlers."""
        event_system.EVENT_HANDLERS.clear()
        called = []
        evt = Event()

        @event_system.register_event_handler("test.bg_multi")
        def handler1(payload):
            called.append(1)

        @event_system.register_event_handler("test.bg_multi")
        def handler2(payload):
            called.append(2)
            evt.set()

        event_system.start_event_executor(max_workers=2)
        event_system.dispatch_background("test.bg_multi", {})

        evt.wait(2)
        assert 1 in called
        assert 2 in called

    def test_dispatch_background_exception_logged(self):
        """Background handler exception is logged."""
        event_system.EVENT_HANDLERS.clear()
        evt = Event()

        @event_system.register_event_handler("test.bg_exc")
        def failing_handler(payload):
            evt.set()
            raise RuntimeError("bg error")

        event_system.start_event_executor(max_workers=1)

        with patch("modules.groups.events.system.logger") as mock_logger:
            event_system.dispatch_background("test.bg_exc", {})
            evt.wait(2)
            # Error should be logged
            assert mock_logger.exception.called or mock_logger.error.called


class TestExecutorLifecycle:
    """Test executor lifecycle management."""

    def teardown_method(self):
        """Cleanup after each test."""
        event_system.shutdown_event_executor(wait=True)
        event_system._executor_shutdown = False
        event_system._EXECUTOR = None

    def test_start_event_executor_creates_executor(self):
        """start_event_executor creates thread pool."""
        event_system.start_event_executor(max_workers=2)
        assert event_system._EXECUTOR is not None

    def test_start_event_executor_with_custom_max_workers(self):
        """start_event_executor accepts custom max_workers."""
        event_system.start_event_executor(max_workers=8)
        assert event_system._EXECUTOR._max_workers == 8

    def test_start_event_executor_idempotent(self):
        """start_event_executor is idempotent."""
        event_system.start_event_executor(max_workers=2)
        executor1 = event_system._EXECUTOR

        event_system.start_event_executor(max_workers=4)
        executor2 = event_system._EXECUTOR

        # Should be same executor (idempotent)
        assert executor1 is executor2

    def test_shutdown_event_executor_stops_executor(self):
        """shutdown_event_executor stops thread pool."""
        event_system.start_event_executor(max_workers=2)
        event_system.shutdown_event_executor(wait=True)

        assert event_system._EXECUTOR is None
        assert event_system._executor_shutdown is True

    def test_shutdown_event_executor_idempotent(self):
        """shutdown_event_executor is idempotent."""
        event_system.start_event_executor(max_workers=2)
        event_system.shutdown_event_executor(wait=True)

        # Should not raise calling again
        event_system.shutdown_event_executor(wait=True)
        assert event_system._executor_shutdown is True

    def test_get_or_create_executor_returns_none_after_shutdown(self):
        """_get_or_create_executor returns None after shutdown."""
        event_system.shutdown_event_executor(wait=True)
        executor = event_system._get_or_create_executor()
        assert executor is None

    def test_dispatch_background_with_lazy_executor(self):
        """dispatch_background creates executor lazily."""
        event_system.EVENT_HANDLERS.clear()
        evt = Event()

        @event_system.register_event_handler("test.lazy")
        def handler(payload):
            evt.set()

        # Don't call start_event_executor, let dispatch_background create it
        event_system.dispatch_background("test.lazy", {})

        assert evt.wait(2), "lazy executor did not start handler"
        event_system.shutdown_event_executor(wait=True)


class TestClearingState:
    """Test clearing event handlers between tests."""

    def test_clearing_handlers(self):
        """EVENT_HANDLERS can be cleared for test isolation."""
        event_system.EVENT_HANDLERS.clear()

        @event_system.register_event_handler("test.clear")
        def handler(p):
            pass

        assert "test.clear" in event_system.EVENT_HANDLERS

        event_system.EVENT_HANDLERS.clear()
        assert len(event_system.EVENT_HANDLERS) == 0
