"""Pinning tests for the ``archive_channel`` buttons on the stale incident channel notice.

The notice posted by the stale-channel job carries the callback id ``archive_channel``
and three buttons (``archive``, ``schedule_retro``, ``ignore``). That id is on a message
already posted in channels, so each test presses a button by sending the
``interactive_message`` payload Slack would send through ``slack_bolt.App.dispatch``.

The ``archive`` value is the rebuilt ``incident.response`` plugin's (TASK-145.8.5.3): it
registers ``incident.response.archive`` with the ``archive_channel`` alias scoped to that
value, attached ahead of the legacy handlers as production attaches it, so ``ignore`` and
``schedule_retro`` still fall through to the legacy listener (their pins prove it). The
archive fixture is rewired to the target's fakes (decisions/migration.md step 4): the
plugin's scope opener resolves an in-memory record store holding the channel's legacy
incident, and the response providers return the core in-memory report, list projection and
conversation, seeded as the legacy edges were (the report and the list row show Open, the
bot a member of the open channel). Sentinel stays faked at the client's ``send_event``.

Named changes, each cited where a pin was edited: the refusal is decided by the record, not
the channel name (kind b); a button press names no locale, so the channel notices and
replies are English then French (kind b, decisions/i18n.md); a channel the bot cannot join
still has its incident closed (kind b, decisions/incident-management.md); one
``incident_channel_archived`` per archive and none on a refusal, with the incident,
conversation, user and time instead of the request body (kinds a and b). The ended
behaviour (two events per archive, an event on a refusal) was pinned in
``test_legacy_only_*`` tests, deleted with it; the new behaviour is tested under
tests/unit/features/incident/response/.
"""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Any

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
)
from features.incident.core.api import ReportReference
from features.incident.response import plugin, providers
from tests.factories.i18n import load_plugin_catalogues, reset_translation_service
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

from .conftest import (
    CHANNEL_ID,
    INCIDENT_CHANNEL_NAME,
    REPORT_DOCUMENT_ID,
    REPORT_URL,
    RESPONSE_URL,
    USER_ID,
    IncidentSurface,
    attach_rebuilt_listeners_first,
    last_view,
    view_text,
)

pytestmark = pytest.mark.integration

NOTICE_TS = "1700000000.000200"
STORE_UNAVAILABLE_MESSAGE = (
    "The incidents database is temporarily unavailable. Please try again later.\n"
    "La base de données des incidents est temporairement indisponible. Veuillez réessayer plus tard."
)
OTHER_CHANNEL_ID = "C0GENERAL"
INCIDENT_ID = "inc-1"
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id=REPORT_DOCUMENT_ID)
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}


@dataclass
class ArchiveSurface:
    """The incident surface with the response plugin registered, read back in domain terms."""

    surface: IncidentSurface
    records: SwitchableRecordStore
    reports: InMemoryIncidentReport
    projection: InMemoryIncidentListProjection
    conversations: InMemoryIncidentConversation

    @property
    def slack(self) -> Any:
        return self.surface.slack

    @property
    def google(self) -> Any:
        return self.surface.google

    def stored_status(self) -> IncidentStatus:
        """The status on the incident's record."""
        found = asyncio.run(record_incident_store(self.records, tenants=TENANTS).get(INCIDENT_ID))
        assert found.data is not None
        return found.data.status

    def report_status(self) -> str:
        """The status the report's status line shows."""
        shown = self.reports.status_text_of(REPORT)
        assert shown is not None
        return shown.value

    def list_status(self) -> str:
        """The status cell of the incident's row in the list sheet."""
        [row] = [row for row in self.projection.rows if row[5] == INCIDENT_ID]
        return row[3]

    def posted_texts(self) -> list[str]:
        """The texts posted to the incident channel, in order."""
        return list(self.conversations.posts_in(slack_conversation(CHANNEL_ID)))

    def archived(self, channel_id: str = CHANNEL_ID) -> bool:
        """Whether the channel is archived."""
        return self.conversations.is_archived(slack_conversation(channel_id))


@pytest.fixture
def surface(incident_surface: IncidentSurface, monkeypatch: pytest.MonkeyPatch) -> Iterator[ArchiveSurface]:
    """An open incident whose channel the bot is a member of, on the legacy edges and the response plugin's fakes.

    The legacy table, report and bookmarks serve the ``ignore`` and ``schedule_retro``
    buttons, which stay legacy; the record store, report, list projection and
    conversation serve the rebuilt ``archive``. The response catalogue is loaded as the
    lifespan loads it.
    """
    incident_surface.table.seed()
    incident_surface.google.add_incident_report()
    incident_surface.slack.client.replies["conversations_info"] = {
        "ok": True,
        "channel": {"id": CHANNEL_ID, "name": INCIDENT_CHANNEL_NAME, "is_member": True},
    }
    incident_surface.slack.client.replies["bookmarks_list"] = {
        "ok": True,
        "bookmarks": [{"title": "Incident report", "link": REPORT_URL}],
    }

    records = SwitchableRecordStore()
    seed_legacy_incident(records, CHANNEL_ID, incident_id=INCIDENT_ID, report_url=REPORT_URL)
    reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0")
    reports.seed_sections(REPORT, [])
    asyncio.run(reports.set_status_text(REPORT, IncidentStatus.OPEN))
    projection = InMemoryIncidentListProjection()
    asyncio.run(projection.append_row(replace(incident_on(CHANNEL_ID, INCIDENT_ID), report=REPORT)))
    archive = ArchiveSurface(
        incident_surface,
        records,
        reports,
        projection,
        InMemoryIncidentConversation(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID, OTHER_CHANNEL_ID]),
    )
    monkeypatch.setattr(providers, "incident_report", lambda: archive.reports)
    monkeypatch.setattr(providers, "incident_list_projection", lambda: archive.projection)
    monkeypatch.setattr(providers, "incident_conversation", lambda: archive.conversations)

    incident_surface.provider.set_scope_opener(incident_scopes(records, tenants=TENANTS))
    plugin.register_slack_commands(registrar=incident_surface.provider)
    attach_rebuilt_listeners_first(incident_surface)
    load_plugin_catalogues(plugin.register_i18n_resources)
    yield archive
    reset_translation_service()


def press(surface: ArchiveSurface, button: str, channel_id: str = CHANNEL_ID) -> Any:
    """Press ``button`` on the stale-channel notice, as Slack sends an interactive message action."""
    return surface.slack.interaction(
        {
            "type": "interactive_message",
            "callback_id": "archive_channel",
            "actions": [{"name": button, "type": "button", "value": button}],
            "channel": {"id": channel_id, "name": INCIDENT_CHANNEL_NAME},
            "message_ts": NOTICE_TS,
            "trigger_id": "trigger-notice",
            "response_url": RESPONSE_URL,
            "original_message": {
                "text": "This channel has been quiet for 14 days",
                "attachments": [{"callback_id": "archive_channel"}],
            },
        }
    )


def sentinel_events(surface: ArchiveSurface) -> list[str]:
    return [event["event"] for event in surface.slack.sentinel_events]


def shown_status(surface: ArchiveSurface) -> str:
    """The status the legacy ``/sre incident show`` renders from the legacy table (ignore and retro stay legacy)."""
    surface.surface.sre("incident show")
    return view_text(last_view(surface.slack.client)).split("*Status*:\n", 1)[1].split("\n", 1)[0]


# ignore


def test_ignore_rewrites_the_notice_without_buttons_and_records_one_sentinel_event(surface: ArchiveSurface) -> None:
    """Ignoring acks empty, replaces the notice with a delay message minus its attachments, and archives nothing."""
    response = press(surface, "ignore")

    assert (response.status, response.body) == (200, "")
    assert surface.slack.client.calls_to("chat_update") == [
        {
            "channel": CHANNEL_ID,
            "text": f"<@{USER_ID}> has delayed scheduling and archiving this channel for 14 days.",
            "ts": NOTICE_TS,
            "attachments": [],
        }
    ]
    assert sentinel_events(surface) == ["incident_channel_archive_delayed"]
    assert surface.slack.client.calls_to("conversations_archive") == []
    assert surface.google.docs.texts[REPORT_DOCUMENT_ID].count("Status: Open") == 1
    assert shown_status(surface) == "Open"


# archive


def test_archive_closes_the_incident_in_the_report_the_sheet_and_the_record(surface: ArchiveSurface) -> None:
    """The archive button closes the incident wherever its status shows."""
    press(surface, "archive")

    assert surface.report_status() == "Closed"
    assert surface.list_status() == "Closed"
    assert surface.stored_status() is IncidentStatus.CLOSED


def test_archive_announces_the_close_then_archives_the_channel(surface: ArchiveSurface) -> None:
    """The channel is told who closed the incident and who archived the channel, before Slack archives it."""
    response = press(surface, "archive")

    assert (response.status, response.body) == (200, "")
    # Named change (kind b, decisions/i18n.md, TASK-145.8.5.3 OQ2): a button press names no
    # locale, so each notice is English then French (the legacy notices were English only).
    assert surface.posted_texts() == [
        f"<@{USER_ID}> has updated the incident status to Closed.\n<@{USER_ID}> a changé le statut de l'incident à Closed.",
        f"<@{USER_ID}> has archived this channel 👋\n<@{USER_ID}> a archivé ce canal 👋",
    ]
    assert surface.archived()
    assert surface.slack.client.calls_to("chat_update") == []


def test_archive_records_the_archive_in_sentinel(surface: ArchiveSurface) -> None:
    """Archiving emits incident_channel_archived and no other event kind."""
    press(surface, "archive")

    assert set(sentinel_events(surface)) == {"incident_channel_archived"}


def test_archive_records_one_event_with_the_incident_the_channel_the_presser_and_the_time(surface: ArchiveSurface) -> None:
    """Named changes (kind a: once per archive; kind b: no request body, decisions/observability.md)."""
    press(surface, "archive")

    [event] = surface.slack.sentinel_events
    assert event["event"] == "incident_channel_archived"
    assert set(event["message"]) == {"incident_id", "conversation_id", "user_id", "at"}
    assert (event["message"]["incident_id"], event["message"]["conversation_id"], event["message"]["user_id"]) == (
        INCIDENT_ID,
        CHANNEL_ID,
        USER_ID,
    )


def test_archive_joins_the_channel_first_when_the_bot_is_not_a_member(surface: ArchiveSurface) -> None:
    """A channel the bot has not joined is joined before the status update and the archive."""
    surface.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, non_member_ids=[CHANNEL_ID])

    press(surface, "archive")

    assert surface.conversations.joined == [slack_conversation(CHANNEL_ID)]
    assert surface.archived()


def test_archive_where_the_bot_cannot_join_closes_the_incident_and_archives_nothing(surface: ArchiveSurface) -> None:
    """Named change (kind b, decisions/incident-management.md, TASK-145.8.5.3 OQ4): a failed join never blocks the record."""
    surface.conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, private_non_member_ids=[CHANNEL_ID])

    press(surface, "archive")

    assert surface.stored_status() is IncidentStatus.CLOSED
    assert not surface.archived()
    assert [message["text"] for message in surface.slack.responses] == [
        "The incident is closed, but I can't join its channel, so nothing was posted there and the channel was not archived.\n"
        "L'incident est fermé, mais je ne peux pas rejoindre son canal; rien n'y a donc été publié et le canal n'a pas été archivé."
    ]
    assert sentinel_events(surface) == []


def test_archive_refuses_a_channel_that_is_not_an_incident_channel(surface: ArchiveSurface) -> None:
    """In a channel with no incident nothing is closed or archived and the presser gets an ephemeral refusal."""
    press(surface, "archive", channel_id=OTHER_CHANNEL_ID)

    # Named change (kind b, decisions/incident-management.md command check, TASK-145.8.5 OQ8): the
    # refusal is decided by the record, not the channel name, so it no longer names the channel;
    # it is English then French (decisions/i18n.md).
    assert surface.slack.client.calls_to("chat_postEphemeral") == [
        {
            "text": "This channel is not an incident channel, so there is no incident to close.\n"
            "Ce canal n'est pas un canal d'incident; il n'y a donc aucun incident à fermer.",
            "channel": OTHER_CHANNEL_ID,
            "user": USER_ID,
        }
    ]
    assert not surface.archived(OTHER_CHANNEL_ID)
    assert surface.conversations.posts_in(slack_conversation(OTHER_CHANNEL_ID)) == ()
    assert surface.report_status() == "Open"
    assert sentinel_events(surface) == []


def test_archive_answers_in_both_languages_and_archives_nothing_when_the_incidents_table_is_down(
    surface: ArchiveSurface,
) -> None:
    """A failing record lookup answers with the bilingual unavailable message and leaves the channel and report alone."""
    surface.records.go_down()

    press(surface, "archive")

    [message] = surface.slack.responses
    assert message["text"] == STORE_UNAVAILABLE_MESSAGE
    assert not surface.archived()
    assert surface.report_status() == "Open"


# schedule_retro


def test_schedule_retro_opens_the_retro_modal_and_records_one_sentinel_event(surface: ArchiveSurface) -> None:
    """The retro button opens the scheduling modal on its trigger and archives nothing."""
    surface.slack.client.replies["conversations_members"] = {"ok": True, "members": [USER_ID]}
    surface.slack.client.replies["users_info"] = {
        "ok": True,
        "user": {"id": USER_ID, "name": "ada", "real_name": "Ada", "locale": "en-US", "profile": {"real_name": "Ada"}},
    }

    response = press(surface, "schedule_retro")

    assert (response.status, response.body) == (200, "")
    [opened] = surface.slack.client.calls_to("views_open")
    assert opened["trigger_id"] == "trigger-notice"
    assert opened["view"]["title"]["text"]
    assert sentinel_events(surface) == ["incident_retro_scheduled"]
    assert surface.slack.client.calls_to("conversations_archive") == []
