"""Pinning tests for the ``/sre incident updates``, ``summary`` and ``add_summary`` commands.

Each test sends a form-encoded slash command through ``slack_bolt.App.dispatch``
on the harness app and asserts only what Slack and the backing seams observe:
the HTTP ack, the message posted to ``response_url``, the Web API calls
(``views_open``, ``chat_postMessage``) made on the fake Slack client, and the
calls recorded on the patched incident store lookups.

The legacy incident handler posts through the SRE platform module's own Web
API client, so that client is replaced with the harness's fake. The incident
store is never reached: the channel lookup and the updates fetch are replaced
with recorders on the module attributes the handler resolves at call time.
"""

import json
from typing import Any

import pytest

from modules.incident import db_operations, incident_folder
from modules.sre.platforms import slack as sre_slack

from .conftest import CHANNEL_ID, RESPONSE_URL, TRIGGER_ID, SlackCommandHarness

pytestmark = pytest.mark.integration

INCIDENT_ID = "incident-42"
STORED_INCIDENT: dict[str, Any] = {"id": {"S": INCIDENT_ID}, "channel_id": {"S": CHANNEL_ID}}
COMMAND_EXECUTED_TEXT = "Incident command executed"
ADD_SUMMARY_DEPRECATION_TEXT = (
    "The `/sre incident add_summary` command is deprecated and will be discontinued after 2025-11-01. "
    "Please use `/sre incident updates add` instead."
)
SUMMARY_DEPRECATION_TEXT = (
    "The `/sre incident summary` command is deprecated and will be discontinued after 2025-11-01. "
    "Please use `/sre incident updates show` instead."
)


class Recorder:
    """Callable fake that records its arguments and returns a fixed value."""

    def __init__(self, returns: Any = None) -> None:
        self.returns = returns
        self.calls: list[tuple[Any, ...]] = []

    def __call__(self, *args: Any) -> Any:
        self.calls.append(args)
        return self.returns


@pytest.fixture
def harness(slack_command_harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch) -> SlackCommandHarness:
    """The command harness with the legacy SRE handler posting through its fake Slack client."""
    monkeypatch.setattr(sre_slack, "client", slack_command_harness.client)
    return slack_command_harness


@pytest.fixture
def incident_lookup(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    """Channel-to-incident lookup answering with one stored incident row."""
    recorder = Recorder(returns=STORED_INCIDENT)
    monkeypatch.setattr(db_operations, "get_incident_by_channel_id", recorder)
    return recorder


def stub_fetch_updates(monkeypatch: pytest.MonkeyPatch, updates: list[str] | None) -> Recorder:
    """Replace the stored-updates fetch with a recorder answering ``updates``."""
    recorder = Recorder(returns=updates)
    monkeypatch.setattr(incident_folder, "fetch_updates", recorder)
    return recorder


def only_response_text(harness: SlackCommandHarness) -> str:
    """Text of the single ephemeral message the command posted back to its response_url."""
    assert len(harness.responses) == 1, harness.responses
    response = harness.responses[0]
    assert response["url"] == RESPONSE_URL
    assert response["response_type"] == "ephemeral"
    text: str = response["text"]
    return text


def assert_updates_modal_opened_for_channel_incident(harness: SlackCommandHarness, incident_lookup: Recorder) -> None:
    """Exactly one updates modal opened on the command's trigger, keyed to the channel's incident."""
    assert incident_lookup.calls == [(CHANNEL_ID,)]
    opened = harness.client.calls_to("views_open")
    assert len(opened) == 1
    assert opened[0]["trigger_id"] == TRIGGER_ID
    view = opened[0]["view"]
    assert view["callback_id"] == "incident_updates_view"
    assert json.loads(view["private_metadata"]) == {"incident_id": INCIDENT_ID, "channel_id": CHANNEL_ID}
    assert harness.client.calls_to("chat_postMessage") == []


def assert_nothing_shown_in_slack(harness: SlackCommandHarness) -> None:
    """No modal opened and no message posted to the channel."""
    assert harness.client.calls_to("views_open") == []
    assert harness.client.calls_to("chat_postMessage") == []


def assert_updates_posted_to_channel(harness: SlackCommandHarness, fetch: Recorder) -> None:
    """The stored updates were fetched for the channel and posted to it exactly once.

    The fetch receives the channel id where an incident id is named; that is
    the current lookup key and is pinned as observed.
    """
    assert fetch.calls == [(CHANNEL_ID,)]
    assert harness.client.calls_to("chat_postMessage") == [{"channel": CHANNEL_ID, "text": "Current updates:\nfirst\nsecond"}]
    assert harness.client.calls_to("views_open") == []


def test_updates_add_opens_the_updates_modal_for_the_channel_incident(
    harness: SlackCommandHarness, incident_lookup: Recorder
) -> None:
    """/sre incident updates add resolves the channel's incident and opens the updates modal.

    The modal carries the incident and channel ids so its submission can store
    the update; nothing else is said back beyond the generic acknowledgement.
    """
    response = harness.dispatch("sre", "incident updates add")

    assert response.status == 200
    assert_updates_modal_opened_for_channel_incident(harness, incident_lookup)
    assert only_response_text(harness) == COMMAND_EXECUTED_TEXT


def test_updates_show_posts_the_stored_updates_to_the_channel(
    harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/sre incident updates show posts every stored update, one per line, in the channel."""
    fetch = stub_fetch_updates(monkeypatch, ["first", "second"])

    response = harness.dispatch("sre", "incident updates show")

    assert response.status == 200
    assert_updates_posted_to_channel(harness, fetch)
    assert only_response_text(harness) == COMMAND_EXECUTED_TEXT


@pytest.mark.parametrize("stored", [[], None], ids=["empty", "missing"])
def test_updates_show_without_stored_updates_says_none_were_found(
    harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch, stored: list[str] | None
) -> None:
    """/sre incident updates show with nothing stored answers privately and posts nothing to the channel."""
    fetch = stub_fetch_updates(monkeypatch, stored)

    response = harness.dispatch("sre", "incident updates show")

    assert response.status == 200
    assert fetch.calls == [(CHANNEL_ID,)]
    assert only_response_text(harness) == "No updates found for this incident."
    assert_nothing_shown_in_slack(harness)


@pytest.mark.parametrize("text", ["incident updates", "incident updates bogus"], ids=["bare", "unknown-action"])
def test_updates_without_a_known_action_replies_with_updates_help(
    harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch, incident_lookup: Recorder, text: str
) -> None:
    """/sre incident updates with no or an unknown action lists the add and show actions only.

    Both store seams are recorders so any lookup would be visible; neither is
    called, and no modal or channel message is produced.
    """
    fetch = stub_fetch_updates(monkeypatch, ["first"])

    response = harness.dispatch("sre", text)

    assert response.status == 200
    reply = only_response_text(harness)
    assert reply.startswith("`/sre incident updates <action>")
    assert "• `add` — add updates to the incident" in reply
    assert "• `show` — show current incident updates" in reply
    assert_nothing_shown_in_slack(harness)
    assert incident_lookup.calls == []
    assert fetch.calls == []


def test_add_summary_warns_it_is_deprecated_and_opens_the_updates_modal(
    harness: SlackCommandHarness, incident_lookup: Recorder
) -> None:
    """/sre incident add_summary points to ``updates add`` and still opens the updates modal."""
    response = harness.dispatch("sre", "incident add_summary")

    assert response.status == 200
    assert only_response_text(harness) == ADD_SUMMARY_DEPRECATION_TEXT
    assert_updates_modal_opened_for_channel_incident(harness, incident_lookup)


def test_summary_warns_it_is_deprecated_and_posts_the_stored_updates(
    harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/sre incident summary points to ``updates show`` and still posts the stored updates to the channel."""
    fetch = stub_fetch_updates(monkeypatch, ["first", "second"])

    response = harness.dispatch("sre", "incident summary")

    assert response.status == 200
    assert only_response_text(harness) == SUMMARY_DEPRECATION_TEXT
    assert_updates_posted_to_channel(harness, fetch)
