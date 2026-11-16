"""The ``/sre incident status`` and ``status update`` Slack entry point.

The handlers run over a scope opener resolving an in-memory record store seeded
with one legacy incident on the channel (its report linked, Slack and Google
configured), and the response providers return the core in-memory report, list
projection and conversation fakes. Replies are read in the invoker's locale from
the real catalogues, which the directory's conftest loads. Assertions read the
reply, the stored status, the report's status line, the list row's status cell
and the channel's posts, which is what the invoker and the channel see.
"""

import asyncio
from typing import Any

import pytest

from contracts.operations.result import OperationResult
from contracts.slack.models import CommandPayload, CommandResponse
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
)
from features.incident.core.api import ReportReference
from features.incident.response import plugin, providers
from features.incident.response.entrypoints.slack import handle_status_command, handle_status_update_command
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import (
    GOOGLE_TENANT,
    SLACK_TENANT,
    SwitchableRecordStore,
    incident_scopes,
    record_incident_store,
    seed_legacy_incident,
    slack_conversation,
)
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit

CHANNEL_ID = "C0INCIDENT"
USER_ID = "U0INVOKER"
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="D0REPORT")
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}


class _Surface:
    """The records, the three fakes behind the response providers, and a way to send the command."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, records: InMemoryRecordStore | None = None) -> None:
        self.records = InMemoryRecordStore() if records is None else records
        seed_legacy_incident(
            self.records, CHANNEL_ID, incident_id="inc-1", report_url="https://docs.google.com/document/d/D0REPORT/edit"
        )
        self.reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0")
        self.reports.seed_sections(REPORT, [])
        self.projection = InMemoryIncidentListProjection()
        self.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID])
        monkeypatch.setattr(providers, "incident_report", lambda: self.reports)
        monkeypatch.setattr(providers, "incident_list_projection", lambda: self.projection)
        monkeypatch.setattr(providers, "incident_conversation", lambda: self.conversations)

    def update(self, text: str, *, channel_id: str = CHANNEL_ID, locale: str = "en-US") -> str:
        payload = CommandPayload(text=text, user_id=USER_ID, channel_id=channel_id, user_locale=locale)
        response = handle_status_update_command(payload, incident_scopes(self.records, tenants=TENANTS))
        assert response.ephemeral
        return response.message

    def stored_status(self) -> IncidentStatus:
        found = asyncio.run(record_incident_store(self.records, tenants=TENANTS).get("inc-1"))
        assert found.data is not None
        return found.data.status

    def posts(self) -> tuple[str, ...]:
        return tuple(self.conversations.posts_in(slack_conversation(CHANNEL_ID)))


@pytest.fixture
def surface(monkeypatch: pytest.MonkeyPatch) -> _Surface:
    return _Surface(monkeypatch)


def test_update_changes_the_record_the_report_the_list_and_tells_the_channel(surface: _Surface) -> None:
    reply = surface.update("Closed")

    assert reply == "The incident status is now Closed."
    assert surface.stored_status() is IncidentStatus.CLOSED
    assert surface.reports.status_text_of(REPORT) is IncidentStatus.CLOSED
    assert [row[3] for row in surface.projection.rows] == ["Closed"]
    assert surface.posts() == (f"<@{USER_ID}> has updated the incident status to Closed.",)


def test_a_status_of_several_words_is_read_whole(surface: _Surface) -> None:
    surface.update("Ready to be Reviewed")

    assert surface.stored_status() is IncidentStatus.READY_TO_BE_REVIEWED


def test_a_french_invoker_reads_the_reply_and_the_notice_in_french(surface: _Surface) -> None:
    reply = surface.update("Reviewed", locale="fr-FR")

    assert reply == "Le statut de l'incident est maintenant Reviewed."
    assert surface.posts() == (f"<@{USER_ID}> a changé le statut de l'incident à Reviewed.",)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("", "Please provide a status to update.", id="missing"),
        pytest.param(
            "Resolved",
            "A valid status must be used with this command:\nIn Progress, Open, Ready to be Reviewed, Reviewed, Closed",
            id="unknown",
        ),
        pytest.param(
            "closed",
            "A valid status must be used with this command:\nIn Progress, Open, Ready to be Reviewed, Reviewed, Closed",
            id="case-sensitive",
        ),
    ],
)
def test_a_missing_or_unknown_status_is_answered_and_nothing_changes(surface: _Surface, text: str, expected: str) -> None:
    assert surface.update(text) == expected
    assert surface.stored_status() is IncidentStatus.OPEN
    assert surface.posts() == ()


def test_outside_an_incident_channel_nothing_changes(surface: _Surface) -> None:
    reply = surface.update("Closed", channel_id="C0OTHER")

    assert reply == "This channel is not an incident channel, so it has no status to change."
    assert surface.stored_status() is IncidentStatus.OPEN
    assert (surface.projection.rows, surface.posts()) == ([], ())


def test_with_the_records_unavailable_nothing_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    records = SwitchableRecordStore()
    surface = _Surface(monkeypatch, records)
    records.go_down()

    reply = surface.update("Closed")

    assert reply == "The incidents database is temporarily unavailable. Please try again later."
    assert surface.reports.status_text_of(REPORT) is None
    assert (surface.projection.rows, surface.posts()) == ([], ())


def test_a_lost_record_guard_asks_to_try_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Another writer wins every guarded update, so the store reports a conflict and nothing else is written."""

    class LostGuard(InMemoryRecordStore):
        def update(self, table: Any, key: Any, changes: Any, *, expected: Any = None) -> OperationResult[Any]:
            return OperationResult.success(data=None)

    surface = _Surface(monkeypatch, LostGuard())

    assert surface.update("Closed") == "The incident changed while its status was being updated. Please try again."
    assert (surface.projection.rows, surface.posts()) == ([], ())


def test_each_follower_that_did_not_write_gets_a_line(monkeypatch: pytest.MonkeyPatch) -> None:
    surface = _Surface(monkeypatch)
    surface.reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0")
    surface.projection = InMemoryIncidentListProjection(fail_with=OperationResult.transient_error("sheets down"))
    surface.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, archived_ids=[CHANNEL_ID])

    reply = surface.update("Closed")

    assert reply.splitlines() == [
        "The incident status is now Closed.",
        "Couldn't update the status line of the incident report.",
        "Couldn't update the status in the incident list.",
        "The incident channel can't be written to, so nothing was posted there.",
    ]


def _status(text: str, locale: str = "en-US") -> CommandResponse:
    return handle_status_command(CommandPayload(text=text, user_id=USER_ID, channel_id=CHANNEL_ID, user_locale=locale))


def test_a_bare_status_points_to_status_update_and_changes_nothing(surface: _Surface) -> None:
    response = _status("Closed")

    assert response.message == "Use `/sre incident status update Closed` to change the status."
    assert (surface.projection.rows, surface.posts()) == ([], ())


@pytest.mark.parametrize("text", ["", "show", "closed"])
def test_status_without_update_answers_its_help(text: str) -> None:
    response = _status(text)

    assert response.ephemeral
    assert response.message == (
        "`/sre incident status update <status>` changes this incident's status.\n"
        "*Valid statuses:* In Progress, Open, Ready to be Reviewed, Reviewed, Closed"
    )


def test_the_hookimpl_registers_status_status_update_and_roles_under_sre_incident() -> None:
    registrar = FakeSlackRegistrar(service_scopes=incident_scopes())

    plugin.register_slack_commands(registrar=registrar)

    assert [(command["parent"], command["command"]) for command in registrar.commands] == [
        ("sre.incident", "status"),
        ("sre.incident.status", "update"),
        ("sre.incident", "roles"),
        ("sre.incident.roles", "manage"),
    ]


def test_without_slack_configured_nothing_is_registered() -> None:
    registrar = FakeSlackRegistrar(service_scopes=incident_scopes(tenants={WorkplaceSystem.GOOGLE: GOOGLE_TENANT}))

    plugin.register_slack_commands(registrar=registrar)

    assert registrar.commands == []


def test_every_registered_command_carries_its_catalogue_keys() -> None:
    registrar = FakeSlackRegistrar(service_scopes=incident_scopes())

    plugin.register_slack_commands(registrar=registrar)

    assert [command["description_key"] for command in registrar.commands] == [
        "incident_response.status.description",
        "incident_response.status.update.description",
        "incident_response.roles.description",
        "incident_response.roles.manage.description",
    ]
