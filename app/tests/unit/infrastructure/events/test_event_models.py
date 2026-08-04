"""Unit tests for infrastructure event models."""

from datetime import datetime
from uuid import uuid4

import pytest

from infrastructure.events.models import Event

pytestmark = pytest.mark.unit


def test_event_creation_defaults() -> None:
    event = Event(event_type="test.event")

    assert event.event_type == "test.event"
    assert event.user_email == ""
    assert event.metadata is None
    assert isinstance(event.timestamp, datetime)
    assert event.correlation_id is not None


def test_event_to_dict(event_factory) -> None:
    event = event_factory(event_type="serialize.event", metadata={"k": "v"})

    serialized = event.to_dict()

    assert serialized["event_type"] == "serialize.event"
    assert serialized["metadata"] == {"k": "v"}
    assert isinstance(serialized["timestamp"], str)
    assert isinstance(serialized["correlation_id"], str)


def test_event_from_dict(event_factory) -> None:
    original = event_factory(event_type="deserialize.event", metadata={"a": 1})

    restored = Event.from_dict(original.to_dict())

    assert restored.event_type == original.event_type
    assert restored.user_email == original.user_email
    assert restored.metadata == original.metadata
    assert restored.correlation_id == original.correlation_id


def test_event_generic_metadata() -> None:
    event = Event[dict[str, int]](event_type="typed.metadata", metadata={"x": 1})

    assert event.metadata == {"x": 1}


def test_event_hash() -> None:
    correlation_id = uuid4()
    timestamp = datetime.now()

    first = Event(event_type="first", correlation_id=correlation_id, timestamp=timestamp)
    second = Event(event_type="second", correlation_id=correlation_id, timestamp=timestamp)

    assert hash(first) == hash(second)
