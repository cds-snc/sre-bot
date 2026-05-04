"""Unit tests for refactored event dispatcher behavior."""

import pytest

from infrastructure.events.dispatcher import (
    clear_handlers,
    dispatch_event,
    register_event_handler,
)
from infrastructure.events.models import Event
from infrastructure.events.registry import EventHandlerRegistry
from infrastructure.events.service import EventDispatcher

pytestmark = pytest.mark.unit


def test_dispatch_event_uses_registry(event_factory) -> None:
    """dispatch_event reads handlers from the registry-backed dispatcher."""
    clear_handlers()
    event = event_factory(event_type="test.registry")

    @register_event_handler("test.registry")
    def _handler(evt):
        return evt.event_type

    result = dispatch_event(event)

    assert result == ["test.registry"]


def test_register_event_handler_decorator_still_works() -> None:
    """Legacy decorator registration remains backward compatible."""
    clear_handlers()

    @register_event_handler("test.decorator")
    def _handler(event):
        return "ok"

    event = Event(event_type="test.decorator")
    results = dispatch_event(event)

    assert results == ["ok"]


def test_event_dispatcher_service_accepts_registry(event_factory) -> None:
    """Service can be instantiated with an explicit registry."""
    registry = EventHandlerRegistry()
    dispatcher = EventDispatcher(registry=registry)
    event = event_factory(event_type="test.explicit")

    @dispatcher.register_handler("test.explicit")
    def _handler(evt):
        return evt.event_type

    assert dispatcher.dispatch(event) == ["test.explicit"]


def test_event_dispatcher_service_dispatch_delegates(event_factory) -> None:
    """Dispatch invokes handlers available in the injected registry."""
    registry = EventHandlerRegistry()
    dispatcher = EventDispatcher(registry=registry)
    event = event_factory(event_type="test.delegates")

    def _handler(evt):
        return evt.event_type

    registry.register("test.delegates", _handler)

    assert dispatcher.dispatch(event) == ["test.delegates"]


def test_legacy_decorator_registration_works(event_factory) -> None:
    """Module-level decorator behavior matches previous usage pattern."""
    clear_handlers()
    event = event_factory(event_type="legacy.test")

    @register_event_handler("legacy.test")
    def _handler(_evt):
        return "legacy"

    assert dispatch_event(event) == ["legacy"]


def test_executor_lifecycle_managed_by_service(event_factory) -> None:
    """Executor lifecycle is managed by EventDispatcher instance state."""
    registry = EventHandlerRegistry()
    dispatcher = EventDispatcher(registry=registry)
    called = []

    @dispatcher.register_handler("test.background")
    def _handler(_evt):
        called.append(True)

    dispatcher.start_executor(max_workers=1)
    dispatcher.dispatch_background(event_factory(event_type="test.background"))
    dispatcher.shutdown_executor(wait=True)

    assert called
