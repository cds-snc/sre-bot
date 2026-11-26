"""The archive entry points: ``/sre incident close`` and the stale notice's archive button.

Each handler runs at the sync edge over an in-memory record store holding the
channel's legacy incident, with the response providers returning the core
in-memory report, list projection and conversation and a recording event sink.
Assertions read what users see (the invoker's reply, the presser's private notice
or ``response_url`` reply, the channel's posts, whether the channel is archived)
and the events sent; the registration is read from the fake registrar.

Both post their channel notices in the instance languages, English then French
unless a test configures them (decisions/languages.md). The command replies in
the invoker's language; a button press names no locale, so its replies are in
the instance languages too.
"""

import asyncio
from dataclasses import replace
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.slack.models import CommandPayload
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
)
from features.incident.core.api import ConversationReference, ReportReference
from features.incident.response import plugin, providers
from features.incident.response.entrypoints.slack_archive import (
    ARCHIVE_CALLBACK_ID,
    handle_archive_press,
    handle_close_command,
)
from features.incident.response.interfaces import ArchivedEvent
from tests.factories.incident import (
    GOOGLE_TENANT,
    SLACK_TENANT,
    SwitchableRecordStore,
    incident_on,
    incident_scopes,
    record_incident_store,
    seed_legacy_incident,
    slack_conversation,
)
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit

CHANNEL_ID = "C0INCIDENT"
OTHER_ID = "C0GENERAL"
USER_ID = "U0PRESSER"
INCIDENT_ID = "inc-1"
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="D0REPORT")
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}
STATUS_NOTICE_BOTH = (
    f"<@{USER_ID}> has updated the incident status to Closed.\n<@{USER_ID}> a changé le statut de l'incident à Closed."
)
ARCHIVED_NOTICE_BOTH = f"<@{USER_ID}> has archived this channel 👋\n<@{USER_ID}> a archivé ce canal 👋"


class _Sink:
    def __init__(self) -> None:
        self.sent: list[ArchivedEvent] = []

    async def send_channel_archived(self, event: ArchivedEvent) -> None:
        self.sent.append(event)


class _Client:
    """The Bolt web client, recording the private notices a refusal posts."""

    def __init__(self) -> None:
        self.ephemerals: list[dict[str, Any]] = []

    def chat_postEphemeral(self, **kwargs: Any) -> dict[str, Any]:  # noqa: N802 -- Slack's method name
        self.ephemerals.append(kwargs)
        return {"ok": True}


class _Surface:
    """The records, the fakes behind the response providers, the event sink, the client and the replies."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        conversations: InMemoryIncidentConversation | None = None,
        *,
        languages: tuple[str, ...] | None = None,
    ) -> None:
        self.records = SwitchableRecordStore()
        seed_legacy_incident(
            self.records, CHANNEL_ID, incident_id=INCIDENT_ID, report_url="https://docs.google.com/document/d/D0REPORT/edit"
        )
        self.reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0")
        self.reports.seed_sections(REPORT, [])
        self.projection = InMemoryIncidentListProjection()
        asyncio.run(self.projection.append_row(replace(incident_on(CHANNEL_ID, INCIDENT_ID), report=REPORT)))
        self.conversations = conversations or InMemoryIncidentConversation(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID, OTHER_ID])
        self.events = _Sink()
        self.client = _Client()
        self.responses: list[str] = []
        self.calls: list[str] = []
        self.scopes = incident_scopes(self.records, tenants=TENANTS, languages=languages)
        monkeypatch.setattr(providers, "incident_report", lambda: self.reports)
        monkeypatch.setattr(providers, "incident_list_projection", lambda: self.projection)
        monkeypatch.setattr(providers, "incident_conversation", lambda: self.conversations)
        monkeypatch.setattr(providers, "archive_event_sink", lambda: self.events)

    def close(self, *, locale: str = "en-US", channel_id: str = CHANNEL_ID) -> str:
        payload = CommandPayload(text="", user_id=USER_ID, channel_id=channel_id, user_locale=locale)
        return handle_close_command(payload, self.scopes).message

    def press(self, channel_id: str = CHANNEL_ID) -> None:
        def ack(**_: Any) -> None:
            self.calls.append("ack")

        def respond(text: str) -> None:
            self.responses.append(text)

        body = {"channel": {"id": channel_id}, "user": {"id": USER_ID}, "actions": [{"value": "archive"}]}
        handle_archive_press(ack, body, self.client, respond, self.scopes)

    def posts(self, channel_id: str = CHANNEL_ID) -> tuple[str, ...]:
        return tuple(self.conversations.posts_in(slack_conversation(channel_id)))

    def archived(self, channel_id: str = CHANNEL_ID) -> bool:
        return self.conversations.is_archived(slack_conversation(channel_id))

    def stored_status(self) -> IncidentStatus:
        found = asyncio.run(record_incident_store(self.records, tenants=TENANTS).get(INCIDENT_ID))
        assert found.data is not None
        return found.data.status


@pytest.fixture
def surface(monkeypatch: pytest.MonkeyPatch) -> _Surface:
    return _Surface(monkeypatch)


def test_the_plugin_registers_the_archive_button_with_the_archive_value_of_the_legacy_notice() -> None:
    registrar = FakeSlackRegistrar(service_scopes=incident_scopes())

    plugin.register_slack_commands(registrar=registrar)

    assert ARCHIVE_CALLBACK_ID in registrar.attachment_actions
    assert registrar.legacy_callback_values == {("archive_channel", "archive"): ARCHIVE_CALLBACK_ID}


def test_close_closes_the_incident_archives_the_channel_and_says_so(surface: _Surface) -> None:
    reply = surface.close()

    assert reply == "The incident is closed and its channel archived."
    assert surface.stored_status() is IncidentStatus.CLOSED
    assert surface.posts() == (
        f"<@{USER_ID}> has updated the incident status to Closed.\n<@{USER_ID}> a changé le statut de l'incident à Closed.",
        f"<@{USER_ID}> has archived this channel 👋\n<@{USER_ID}> a archivé ce canal 👋",
    )
    assert surface.archived()
    assert [event.incident_id for event in surface.events.sent] == [INCIDENT_ID]


def test_a_french_invoker_reads_the_reply_in_french_and_the_notices_in_the_instance_languages(surface: _Surface) -> None:
    reply = surface.close(locale="fr-FR")

    assert reply == "L'incident est fermé et son canal archivé."
    assert surface.posts() == (
        f"<@{USER_ID}> has updated the incident status to Closed.\n<@{USER_ID}> a changé le statut de l'incident à Closed.",
        f"<@{USER_ID}> has archived this channel 👋\n<@{USER_ID}> a archivé ce canal 👋",
    )


def test_close_in_a_channel_with_no_incident_closes_and_archives_nothing(surface: _Surface) -> None:
    reply = surface.close(channel_id=OTHER_ID)

    assert reply == "This channel is not an incident channel, so there is no incident to close."
    assert not surface.archived(OTHER_ID)
    assert surface.posts(OTHER_ID) == ()
    assert surface.events.sent == []


def test_close_where_the_bot_cannot_join_still_closes_the_incident_and_says_why_nothing_was_archived(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    surface = _Surface(monkeypatch, InMemoryIncidentConversation(tenant=SLACK_TENANT, private_non_member_ids=[CHANNEL_ID]))

    reply = surface.close()

    assert reply.splitlines() == [
        "The incident status is now Closed.",
        "The incident is closed, but I can't join its channel, so nothing was posted there and the channel was not archived.",
    ]
    assert surface.stored_status() is IncidentStatus.CLOSED
    assert not surface.archived()


def test_close_with_the_records_unavailable_changes_nothing(surface: _Surface) -> None:
    surface.records.go_down()

    reply = surface.close()

    assert reply == "The incidents database is temporarily unavailable. Please try again later."
    assert not surface.archived()


def test_the_button_acks_first_announces_in_both_languages_archives_and_replies_nothing(surface: _Surface) -> None:
    surface.press()

    assert surface.calls == ["ack"]
    assert surface.posts() == (STATUS_NOTICE_BOTH, ARCHIVED_NOTICE_BOTH)
    assert surface.archived()
    assert surface.responses == []
    assert surface.client.ephemerals == []
    assert len(surface.events.sent) == 1


def test_the_button_follows_the_instance_languages_and_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """A French-first instance puts French first in both channel notices (decisions/languages.md)."""
    surface = _Surface(monkeypatch, languages=("fr-FR", "en-US"))

    surface.press()

    assert surface.posts() == (
        f"<@{USER_ID}> a changé le statut de l'incident à Closed.\n<@{USER_ID}> has updated the incident status to Closed.",
        f"<@{USER_ID}> a archivé ce canal 👋\n<@{USER_ID}> has archived this channel 👋",
    )


def test_the_close_command_follows_the_instance_languages_and_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """An English invoker on a French-first instance reads an English reply and French-first channel notices."""
    surface = _Surface(monkeypatch, languages=("fr-FR", "en-US"))

    reply = surface.close()

    assert reply == "The incident is closed and its channel archived."
    assert surface.posts() == (
        f"<@{USER_ID}> a changé le statut de l'incident à Closed.\n<@{USER_ID}> has updated the incident status to Closed.",
        f"<@{USER_ID}> a archivé ce canal 👋\n<@{USER_ID}> has archived this channel 👋",
    )


def test_a_one_language_instance_answers_a_press_in_that_language_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """A press names no locale, so its private refusal is in the instance languages too."""
    surface = _Surface(monkeypatch, languages=("en-US",))

    surface.press(OTHER_ID)

    assert [call["text"] for call in surface.client.ephemerals] == [
        "This channel is not an incident channel, so there is no incident to close."
    ]


def test_the_button_in_a_channel_with_no_incident_tells_the_presser_privately_in_both_languages(surface: _Surface) -> None:
    surface.press(OTHER_ID)

    assert surface.client.ephemerals == [
        {
            "channel": OTHER_ID,
            "user": USER_ID,
            "text": "This channel is not an incident channel, so there is no incident to close.\n"
            "Ce canal n'est pas un canal d'incident; il n'y a donc aucun incident à fermer.",
        }
    ]
    assert not surface.archived(OTHER_ID)
    assert surface.events.sent == []


def test_the_button_with_the_records_unavailable_answers_in_both_languages(surface: _Surface) -> None:
    surface.records.go_down()

    surface.press()

    assert surface.responses == [
        "The incidents database is temporarily unavailable. Please try again later.\n"
        "La base de données des incidents est temporairement indisponible. Veuillez réessayer plus tard."
    ]
    assert not surface.archived()


def test_a_failed_archive_after_the_button_is_told_to_the_presser(monkeypatch: pytest.MonkeyPatch) -> None:
    class ArchiveRefused(InMemoryIncidentConversation):
        async def archive(self, conversation: ConversationReference) -> OperationResult[None]:
            return OperationResult.permanent_error("Slack archive failed: restricted_action", ErrorCode.CONVERSATION_NOT_WRITABLE)

    surface = _Surface(monkeypatch, ArchiveRefused(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID]))

    surface.press()

    assert surface.responses == [
        "The incident is closed, but its channel couldn't be archived.\n"
        "L'incident est fermé, mais son canal n'a pas pu être archivé."
    ]
    assert surface.stored_status() is IncidentStatus.CLOSED
    assert surface.events.sent == []
