"""``SentinelArchiveEventSink``: the archived event's wire shape and its failure handling.

The Sentinel client's ``send_event`` is the external edge, replaced by a recorder
or a raising stub. Assertions are on the payload Sentinel would receive (the legacy
``{event, message}`` envelope with only the incident, conversation, user and time,
never a request body) and on a failed send being absorbed, since the archive must
never fail on its event.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from features.incident.response.adapters.sentinel import SentinelArchiveEventSink
from features.incident.response.interfaces import ArchivedEvent
from integrations.sentinel import client as sentinel_client

pytestmark = pytest.mark.unit

EVENT = ArchivedEvent(
    incident_id="inc-1", conversation_id="C0INCIDENT", user_id="U0PRESSER", at=datetime(2026, 11, 17, 15, 0, tzinfo=UTC)
)


async def test_the_event_carries_only_the_incident_the_conversation_the_user_and_the_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[Any] = []
    monkeypatch.setattr(sentinel_client, "send_event", lambda payload: sent.append(payload) or True)

    await SentinelArchiveEventSink().send_channel_archived(EVENT)

    assert sent == [
        {
            "event": "incident_channel_archived",
            "message": {
                "incident_id": "inc-1",
                "conversation_id": "C0INCIDENT",
                "user_id": "U0PRESSER",
                "at": "2026-11-17T15:00:00+00:00",
            },
        }
    ]


async def test_a_failed_send_is_absorbed(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(payload: Any) -> bool:
        raise ConnectionError("sentinel unreachable")

    monkeypatch.setattr(sentinel_client, "send_event", refuse)

    await SentinelArchiveEventSink().send_channel_archived(EVENT)
