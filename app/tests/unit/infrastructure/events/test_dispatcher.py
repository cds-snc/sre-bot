"""Unit tests for infrastructure event dispatcher."""

import pytest
from unittest.mock import MagicMock

from infrastructure.events.dispatcher import (
    clear_handlers,
    dispatch_event,
    get_handlers_for_event,
    get_registered_events,
    register_event_handler,
)

pytestmark = pytest.mark.unit


class TestEventRegistration:
    """Test event handler registration."""

    def test_register_single_handler(self, event_factory, mock_event_handler):
        """Handler decorator registers handler for event type."""
        clear_handlers()
        decorated = register_event_handler("test.event")(mock_event_handler)

        assert decorated is mock_event_handler
        assert "test.event" in get_registered_events()
        assert mock_event_handler in get_handlers_for_event("test.event")

    def test_register_multiple_handlers_same_event(self, mock_event_handler):
        """Multiple handlers can register for same event type."""
        clear_handlers()
        handler1 = MagicMock()
        handler2 = MagicMock()

        register_event_handler("test.multi")(handler1)
        register_event_handler("test.multi")(handler2)

        handlers = get_handlers_for_event("test.multi")
        assert len(handlers) == 2
        assert handler1 in handlers
        assert handler2 in handlers

    def test_register_handler_returns_original_function(self):
        """Decorator returns original function."""
        clear_handlers()

        def original_handler(event):
            return event

        decorated = register_event_handler("test.return")(original_handler)
        assert decorated is original_handler

    def test_get_registered_events_empty(self):
        """get_registered_events returns empty list when no handlers."""
        clear_handlers()
        assert get_registered_events() == []

    def test_get_registered_events_with_handlers(self):
        """get_registered_events returns list of event types."""
        clear_handlers()

        @register_event_handler("event.one")
        def h1(e):
            pass

        @register_event_handler("event.two")
        def h2(e):
            pass

        events = get_registered_events()
        assert "event.one" in events
        assert "event.two" in events

    def test_get_handlers_for_event(self):
        """get_handlers_for_event returns handlers for event type."""
        clear_handlers()

        handler1 = MagicMock()
        handler2 = MagicMock()

        register_event_handler("test.get")(handler1)
        register_event_handler("test.get")(handler2)

        handlers = get_handlers_for_event("test.get")
        assert len(handlers) == 2
        assert handler1 in handlers
        assert handler2 in handlers

    def test_get_handlers_for_unregistered_event(self):
        """get_handlers_for_event returns empty list for unregistered event."""
        clear_handlers()
        assert get_handlers_for_event("nonexistent") == []


class TestEventDispatch:
    """Test synchronous event dispatch."""

    def test_dispatch_calls_registered_handlers(
        self, event_factory, mock_event_handler
    ):
        """Event dispatch calls all registered handlers."""
        clear_handlers()
        event = event_factory(event_type="test.event")
        register_event_handler("test.event")(mock_event_handler)

        dispatch_event(event)

        mock_event_handler.assert_called_once_with(event)

    def test_dispatch_multiple_handlers_for_same_event(self, event_factory):
        """Dispatch calls multiple handlers for same event type."""
        clear_handlers()
        handler1 = MagicMock(return_value="result1")
        handler2 = MagicMock(return_value="result2")
        event = event_factory(event_type="test.event")

        register_event_handler("test.event")(handler1)
        register_event_handler("test.event")(handler2)

        results = dispatch_event(event)

        handler1.assert_called_once_with(event)
        handler2.assert_called_once_with(event)
        assert len(results) == 2
        assert "result1" in results
        assert "result2" in results

    def test_dispatch_no_handlers_does_not_raise(self, event_factory):
        """Dispatch with no registered handlers doesn't raise."""
        clear_handlers()
        event = event_factory(event_type="unregistered.event")

        # Should not raise
        results = dispatch_event(event)
        assert results == []

    def test_dispatch_exception_in_handler_does_not_stop_others(self, event_factory):
        """Exception in one handler doesn't prevent others from running."""
        clear_handlers()
        handler1 = MagicMock(side_effect=ValueError("Handler error"))
        handler2 = MagicMock(return_value="success")
        event = event_factory(event_type="test.event")

        register_event_handler("test.event")(handler1)
        register_event_handler("test.event")(handler2)

        results = dispatch_event(event)

        handler1.assert_called_once_with(event)
        handler2.assert_called_once_with(event)
        assert "success" in results

    def test_dispatch_returns_handler_results(self, event_factory):
        """Dispatch returns list of handler return values."""
        clear_handlers()

        @register_event_handler("test.event")
        def handler1(e):
            return "result1"

        @register_event_handler("test.event")
        def handler2(e):
            return "result2"

        event = event_factory(event_type="test.event")
        results = dispatch_event(event)

        assert len(results) == 2
        assert "result1" in results
        assert "result2" in results

    def test_dispatch_with_different_event_types(self, event_factory):
        """Different event types call different handlers."""
        clear_handlers()
        handler1 = MagicMock()
        handler2 = MagicMock()

        register_event_handler("event.type1")(handler1)
        register_event_handler("event.type2")(handler2)

        event1 = event_factory(event_type="event.type1")
        event2 = event_factory(event_type="event.type2")

        dispatch_event(event1)
        dispatch_event(event2)

        handler1.assert_called_once_with(event1)
        handler2.assert_called_once_with(event2)
