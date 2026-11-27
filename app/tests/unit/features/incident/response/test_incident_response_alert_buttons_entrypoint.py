"""The alert buttons: ``call-incident`` opens the declare form, ``ignore-incident`` counts once and replaces the buttons.

The handler runs over a scope opener resolving an in-memory record store holding one
webhook item and an in-memory claims store (Slack configured, English then French
shared); the report provider is the core in-memory report and the event sink a
recorder. The fake reply records the views and the message update. Assertions read
the webhook's stored ``acknowledged_count``, the rewritten alert and the events.

Rules under test (reliability.md: a claim per message; webhooks.md section 8: the
count is approximate and never blocks the click): the first ignore of a message
counts one, a repeat press counts nothing and still replaces the buttons; a count
that fails (the webhook is gone) is logged and the buttons are still replaced; an
unknown button only acks.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.in_memory import InMemoryIncidentReport
from features.incident.response import providers
from features.incident.response.adapters.alert_acknowledgements import WEBHOOKS_TABLE
from features.incident.response.entrypoints.slack_declare import handle_alert_button
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import SLACK_TENANT, incident_scopes
from tests.factories.slack import FakeSlackReply

pytestmark = pytest.mark.unit

USER = "U0PRESSER"
CHANNEL = "C0ALERTS"
TS = "1700000000.000100"
IGNORED = f"🙈  <@{USER}> has acknowledged and ignored the incident.\n<@{USER}> a pris connaissance et ignoré l'incident."


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def send(self, event: str, message: Any) -> None:
        self.events.append(event)


@dataclass
class World:
    records: InMemoryRecordStore
    reply: FakeSlackReply
    sink: RecordingSink
    scopes: Any
    acks: list[dict[str, Any]]

    def press(self, name: str, value: str = "hook-1", **body: Any) -> None:
        payload = {
            "actions": [{"name": name, "value": value}],
            "user": {"id": USER},
            "channel": {"id": CHANNEL},
            "message_ts": TS,
            "trigger_id": "T0ALERT",
            "original_message": {
                "ts": TS,
                "text": "Disk full",
                "attachments": [{"callback_id": "handle_incident_action_buttons"}],
            },
            **body,
        }
        handle_alert_button(lambda **kwargs: self.acks.append(kwargs), payload, self.reply, self.scopes)

    def count(self, webhook_id: str = "hook-1") -> int | None:
        item = self.records.get(WEBHOOKS_TABLE, {"id": webhook_id}).data
        return None if item is None else int(item.get("acknowledged_count", 0))


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    records = InMemoryRecordStore()
    records.put(WEBHOOKS_TABLE, {"id": "hook-1", "name": "alerts"})
    sink = RecordingSink()
    monkeypatch.setattr(providers, "declare_event_sink", lambda: sink)
    monkeypatch.setattr(providers, "incident_report", lambda: InMemoryIncidentReport(placements=(("F0FORMS", "Forms"),)))
    yield World(records, FakeSlackReply(), sink, incident_scopes(records, tenants={WorkplaceSystem.SLACK: SLACK_TENANT}), [])


def test_the_first_ignore_counts_one_and_replaces_the_buttons_with_who_ignored(world: World) -> None:
    world.press("ignore-incident")

    assert world.acks == [{}]
    assert world.count() == 1
    [update] = world.reply.calls_to("update_message")
    assert (update["channel_id"], update["ts"], update["text"]) == (CHANNEL, TS, "Disk full")
    assert update["attachments"] == [{"color": "3AA3E3", "fallback": IGNORED, "text": IGNORED}]
    assert world.sink.events == ["ignore_incident_button_pressed"]


def test_a_repeat_ignore_of_the_same_message_counts_nothing_more_and_still_replaces_the_buttons(world: World) -> None:
    world.press("ignore-incident")
    world.press("ignore-incident")

    assert world.count() == 1
    assert len(world.reply.calls_to("update_message")) == 2


def test_an_ignore_on_another_message_counts_again(world: World) -> None:
    world.press("ignore-incident")
    world.press("ignore-incident", message_ts="1700000000.000200")

    assert world.count() == 2


def test_an_ignore_whose_webhook_is_gone_creates_nothing_and_still_replaces_the_buttons(world: World) -> None:
    world.press("ignore-incident", value="hook-deleted")

    assert world.count("hook-deleted") is None
    assert len(world.reply.calls_to("update_message")) == 1


def test_the_buttons_are_read_from_the_container_when_the_payload_names_no_channel(world: World) -> None:
    world.press("ignore-incident", channel={}, message_ts="", container={"channel_id": CHANNEL, "message_ts": TS})

    [update] = world.reply.calls_to("update_message")
    assert (update["channel_id"], update["ts"]) == (CHANNEL, TS)


def test_call_incident_opens_the_form_named_after_the_alert_with_its_location(world: World) -> None:
    world.press("call-incident", value="Disk full on prod")

    assert world.acks == [{}]
    [opened] = world.reply.calls_to("open_view")
    assert opened["trigger_id"] == "T0ALERT"
    [updated] = world.reply.calls_to("update_view")
    name = next(block for block in updated["view"]["blocks"] if block.get("block_id") == "name")
    assert name["element"]["initial_value"] == "Disk full on prod"
    assert updated["view"]["private_metadata"] == f'{{"source_channel_id": "{CHANNEL}", "source_message_ts": "{TS}"}}'
    assert world.sink.events == ["call_incident_button_pressed"]


def test_an_unknown_button_only_acks(world: World) -> None:
    world.press("snooze")

    assert world.acks == [{}]
    assert world.reply.calls == []
    assert world.count() == 0
    assert world.sink.events == []
