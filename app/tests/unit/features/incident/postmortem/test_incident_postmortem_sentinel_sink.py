"""``SentinelPostmortemEventSink``: the scheduled event's wire shape and its failure handling.

The Sentinel client's ``send_event`` is the external edge, replaced by a recorder
or a raising stub. Assertions are on the payload Sentinel would receive: the legacy
event name ``incident_retro_scheduled`` kept for existing queries, and only the
incident, conversation, user, meeting and time (never a request body); a failed send
is absorbed, since a booking must never fail on its event.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from features.incident.postmortem.adapters.sentinel import SentinelPostmortemEventSink
from features.incident.postmortem.interfaces import MeetingScheduledEvent
from integrations.sentinel import client as sentinel_client

pytestmark = pytest.mark.unit

EVENT = MeetingScheduledEvent(
    incident_id="inc-1",
    conversation_id="C0INCIDENT",
    user_id="U0ASKER",
    meeting_id="abc123",
    at=datetime(2026, 12, 1, 15, 0, tzinfo=UTC),
)


async def test_the_event_keeps_its_name_and_carries_only_the_named_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[Any] = []
    monkeypatch.setattr(sentinel_client, "send_event", lambda payload: sent.append(payload) or True)

    await SentinelPostmortemEventSink().send_meeting_scheduled(EVENT)

    assert sent == [
        {
            "event": "incident_retro_scheduled",
            "message": {
                "incident_id": "inc-1",
                "conversation_id": "C0INCIDENT",
                "user_id": "U0ASKER",
                "meeting_id": "abc123",
                "at": "2026-12-01T15:00:00+00:00",
            },
        }
    ]


async def test_a_failed_send_is_absorbed(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(payload: Any) -> bool:
        raise ConnectionError("sentinel unreachable")

    monkeypatch.setattr(sentinel_client, "send_event", refuse)

    await SentinelPostmortemEventSink().send_meeting_scheduled(EVENT)
