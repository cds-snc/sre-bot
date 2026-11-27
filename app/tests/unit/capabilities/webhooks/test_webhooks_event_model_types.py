"""Unit tests for the canonical event model: frozen values, CloudEvents names, typed data.

Events are built directly from the domain types; no engine runs.
"""

import dataclasses
from datetime import datetime

import pytest

from capabilities.webhooks.domain.events import (
    LOCAL_EVENT_ID_PREFIX,
    Alert,
    EventType,
    InboundEvent,
    Notification,
    local_event_id,
)
from contracts.languages import MultilingualText
from tests.unit.capabilities.webhooks.conftest import RECEIVED_AT

pytestmark = pytest.mark.unit

TEXT = MultilingualText((("en-US", "Title"),))


def _alert() -> Alert:
    return Alert(title=TEXT, summary=TEXT, attributes={"budget": "sandbox"})


def test_an_event_carries_the_cloudevents_attributes() -> None:
    event = InboundEvent(id="msg-1", source="inst-1", type=EventType.ALERT, time=RECEIVED_AT, data=_alert())

    assert (event.id, event.source, event.type, event.time, event.subject) == (
        "msg-1",
        "inst-1",
        EventType.ALERT,
        RECEIVED_AT,
        None,
    )


def test_events_and_their_data_are_frozen() -> None:
    alert = _alert()
    event = InboundEvent(id="msg-1", source="inst-1", type=EventType.ALERT, time=RECEIVED_AT, data=alert)

    with pytest.raises(dataclasses.FrozenInstanceError):
        event.type = EventType.NOTIFICATION  # type: ignore[misc]
    with pytest.raises(TypeError):
        alert.attributes["budget"] = "other"  # type: ignore[index]


def test_an_event_type_must_match_its_data() -> None:
    with pytest.raises(ValueError, match="Notification"):
        InboundEvent(id="msg-1", source="inst-1", type=EventType.NOTIFICATION, time=RECEIVED_AT, data=_alert())


def test_an_event_time_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone"):
        InboundEvent(id="msg-1", source="inst-1", type=EventType.ALERT, time=datetime(2026, 1, 1), data=_alert())


def test_a_local_event_id_is_prefixed_and_unique() -> None:
    first, second = local_event_id(), local_event_id()

    assert first.startswith(LOCAL_EVENT_ID_PREFIX) and second.startswith(LOCAL_EVENT_ID_PREFIX)
    assert first != second


def test_a_notification_defaults_to_no_details_and_no_links() -> None:
    notification = Notification(title=TEXT, summary=TEXT)

    assert (notification.details, notification.links, dict(notification.attributes)) == (None, (), {})
