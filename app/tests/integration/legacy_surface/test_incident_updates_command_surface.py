"""Pinning tests for the retired ``/sre incident updates``, ``summary`` and ``add_summary`` commands.

Each test sends a form-encoded slash command through ``slack_bolt.App.dispatch``
on the harness app and asserts only what Slack and the backing seams observe:
the HTTP ack, the message posted to ``response_url``, the Web API calls
(``views_open``, ``chat_postMessage``) made on the fake Slack client, and the
calls recorded on the incident store lookups.

``/sre incident updates`` answers every action with a bilingual pointer to
``/sre incident status-update``; ``summary`` and ``add_summary`` fall to the
incident dispatcher's unknown-command reply. That ``status-update`` stays
registered is pinned by ``test_registered_command_tree_is_unchanged``.

The legacy incident handler posts through the SRE platform module's own Web
API client, so that client is replaced with the harness's fake. The incident
store lookups are replaced with recorders on the module attributes the legacy
paths resolve at call time, so any store access would be recorded.
"""

from dataclasses import dataclass
from typing import Any

import pytest

from modules.incident import db_operations
from modules.sre.platforms import slack as sre_slack

from .conftest import RESPONSE_URL, SlackCommandHarness

pytestmark = pytest.mark.integration

UPDATES_RETIRED_POINTER = (
    "`/sre incident updates` has been retired. "
    "Use `/sre incident status-update` to draft, review and approve a public status update."
    "\n\n"
    "`/sre incident updates` a été retirée. "
    "Utilisez `/sre incident status-update` pour rédiger, réviser et approuver une mise à jour publique."
)


class Recorder:
    """Callable fake that records its arguments and returns a fixed value."""

    def __init__(self, returns: Any = None) -> None:
        self.returns = returns
        self.calls: list[tuple[Any, ...]] = []

    def __call__(self, *args: Any) -> Any:
        self.calls.append(args)
        return self.returns


@dataclass(frozen=True)
class IncidentStore:
    """Recorders standing in for every incident store read the legacy paths used."""

    channel_lookup: Recorder
    field_lookup: Recorder
    adapter_builder: Recorder

    def assert_untouched(self) -> None:
        assert self.channel_lookup.calls == []
        assert self.field_lookup.calls == []
        assert self.adapter_builder.calls == []


@pytest.fixture
def harness(slack_command_harness: SlackCommandHarness, monkeypatch: pytest.MonkeyPatch) -> SlackCommandHarness:
    """The command harness with the legacy SRE handler posting through its fake Slack client."""
    monkeypatch.setattr(sre_slack, "client", slack_command_harness.client)
    return slack_command_harness


@pytest.fixture
def incident_store(monkeypatch: pytest.MonkeyPatch) -> IncidentStore:
    """Record the channel lookup, the field lookup and the DynamoDB adapter builder."""
    store = IncidentStore(
        channel_lookup=Recorder(returns={"id": {"S": "incident-42"}}),
        field_lookup=Recorder(returns=[{"incident_updates": {"L": [{"S": "stored update"}]}}]),
        adapter_builder=Recorder(),
    )
    monkeypatch.setattr(db_operations, "get_incident_by_channel_id", store.channel_lookup)
    monkeypatch.setattr(db_operations, "lookup_incident", store.field_lookup)
    monkeypatch.setattr(db_operations, "build_dynamodb_adapter", store.adapter_builder)
    return store


def only_response_text(harness: SlackCommandHarness) -> str:
    """Text of the single ephemeral message the command posted back to its response_url."""
    assert len(harness.responses) == 1, harness.responses
    response = harness.responses[0]
    assert response["url"] == RESPONSE_URL
    assert response["response_type"] == "ephemeral"
    text: str = response["text"]
    return text


def assert_nothing_shown_in_slack(harness: SlackCommandHarness) -> None:
    """No modal opened and no message posted to the channel."""
    assert harness.client.calls_to("views_open") == []
    assert harness.client.calls_to("chat_postMessage") == []


@pytest.mark.parametrize(
    "text",
    ["incident updates add", "incident updates show", "incident updates", "incident updates bogus"],
    ids=["add", "show", "bare", "unknown-action"],
)
def test_updates_with_any_action_points_to_status_update(
    harness: SlackCommandHarness, incident_store: IncidentStore, text: str
) -> None:
    """/sre incident updates answers every action with the EN/FR pointer to /sre incident status-update.

    The pointer is the whole reply; no modal opens, nothing is posted to the
    channel and the incident store is never read.
    """
    response = harness.dispatch("sre", text)

    assert response.status == 200
    assert only_response_text(harness) == UPDATES_RETIRED_POINTER
    assert_nothing_shown_in_slack(harness)
    incident_store.assert_untouched()


@pytest.mark.parametrize("command", ["summary", "add_summary"])
def test_removed_summary_commands_answer_unknown_command(
    harness: SlackCommandHarness, incident_store: IncidentStore, command: str
) -> None:
    """/sre incident summary and add_summary are no longer handled and get the unknown-command reply.

    No modal opens, nothing is posted to the channel and the incident store is
    never read.
    """
    response = harness.dispatch("sre", f"incident {command}")

    assert response.status == 200
    assert only_response_text(harness) == f"Unknown command: {command}. Type `/sre incident help` to see a list of commands."
    assert_nothing_shown_in_slack(harness)
    incident_store.assert_untouched()
