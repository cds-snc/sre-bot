"""Unit tests for the event handler registrar Protocol in contracts.plugins.

A Protocol-conformant fake registrar receives a handler through the contract
and the recorded call is asserted. The real infrastructure EventDispatcher is
assigned to the Protocol type (checked statically by mypy) and a handler
registered through it is delivered an event, which shows it implements the
contract.
"""

from collections.abc import Callable
from typing import Any

import pytest

from contracts.plugins.hookspecs import EventHandlerRegistrar
from infrastructure.events import Event
from infrastructure.events.service import EventDispatcher

pytestmark = pytest.mark.unit


class _FakeRegistrar:
    """Records every handler registration it receives."""

    def __init__(self) -> None:
        self.handlers: list[tuple[str, Callable[[Any], object]]] = []

    def register_handler(self, event_type: str, handler: Callable[[Any], object]) -> None:
        self.handlers.append((event_type, handler))


def _handler(event: object) -> None:
    return None


def test_fake_registrar_satisfies_the_protocol_and_records_the_handler() -> None:
    fake = _FakeRegistrar()
    registrar: EventHandlerRegistrar = fake

    registrar.register_handler("thing.happened", _handler)

    assert fake.handlers == [("thing.happened", _handler)]


def test_event_dispatcher_implements_the_registrar_protocol() -> None:
    dispatcher = EventDispatcher()
    registrar: EventHandlerRegistrar = dispatcher
    received: list[object] = []

    registrar.register_handler("thing.happened", received.append)
    event = Event(event_type="thing.happened")
    dispatcher.dispatch(event)

    assert received == [event]
