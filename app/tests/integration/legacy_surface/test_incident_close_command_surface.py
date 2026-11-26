"""Pinning tests for ``/sre incident close``.

Each test sends ``/sre incident close`` from a channel through ``slack_bolt.App.dispatch``,
and the provider routes it to the rebuilt ``incident.response`` plugin (TASK-145.8.5.3),
which closes the incident through the same service as the stale notice's archive button.
These pins were first run against the legacy ``close_incident`` on its own edges (the
report's status line, the sheet row, the channel's posts, the archive, the reply when the
table is down) and then rewired to the target's fakes (decisions/migration.md step 4): the
plugin's scope opener resolves an in-memory record store holding the channel's legacy
incident, and the response providers return the core in-memory report, list projection and
conversation, seeded as the legacy edges were.

Named changes, cited where a pin was edited: the command names the invoker's locale, so a
refusal is in that one language (kind b, decisions/i18n.md; the legacy reply was English and
French), a channel with no incident record is refused by the record (kind b), and the
status and archived notices are in the instance languages (kind b, decisions/languages.md).
"""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, replace

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

from .conftest import CHANNEL_ID, REPORT_DOCUMENT_ID, REPORT_URL, USER_ID, IncidentSurface

pytestmark = pytest.mark.integration

INCIDENT_ID = "inc-1"
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id=REPORT_DOCUMENT_ID)
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}


@dataclass
class CloseSurface:
    """The incident surface with the response plugin registered, read back in domain terms."""

    surface: IncidentSurface
    records: SwitchableRecordStore
    reports: InMemoryIncidentReport
    projection: InMemoryIncidentListProjection
    conversations: InMemoryIncidentConversation

    def close(self) -> None:
        self.surface.sre("incident close")

    def report_status(self) -> str:
        shown = self.reports.status_text_of(REPORT)
        assert shown is not None
        return shown.value

    def list_status(self) -> str:
        [row] = [row for row in self.projection.rows if row[5] == INCIDENT_ID]
        return row[3]

    def stored_status(self) -> IncidentStatus:
        found = asyncio.run(record_incident_store(self.records, tenants=TENANTS).get(INCIDENT_ID))
        assert found.data is not None
        return found.data.status

    def channel_messages(self) -> list[str]:
        return list(self.conversations.posts_in(slack_conversation(CHANNEL_ID)))

    def archived(self) -> bool:
        return self.conversations.is_archived(slack_conversation(CHANNEL_ID))

    def replies(self) -> list[str]:
        return [str(message["text"]) for message in self.surface.slack.responses]


@pytest.fixture
def unseeded(incident_surface: IncidentSurface, monkeypatch: pytest.MonkeyPatch) -> Iterator[CloseSurface]:
    """The response plugin's commands over the core in-memory fakes: the report and the list row show Open, the channel is open."""
    records = SwitchableRecordStore()
    reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0")
    reports.seed_sections(REPORT, [])
    asyncio.run(reports.set_status_text(REPORT, IncidentStatus.OPEN))
    projection = InMemoryIncidentListProjection()
    asyncio.run(projection.append_row(replace(incident_on(CHANNEL_ID, INCIDENT_ID), report=REPORT)))
    conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT, open_ids=[CHANNEL_ID])
    monkeypatch.setattr(providers, "incident_report", lambda: reports)
    monkeypatch.setattr(providers, "incident_list_projection", lambda: projection)
    monkeypatch.setattr(providers, "incident_conversation", lambda: conversations)

    incident_surface.provider.set_scope_opener(incident_scopes(records, tenants=TENANTS))
    plugin.register_slack_commands(registrar=incident_surface.provider)
    load_plugin_catalogues(plugin.register_i18n_resources)
    yield CloseSurface(incident_surface, records, reports, projection, conversations)
    reset_translation_service()


@pytest.fixture
def surface(unseeded: CloseSurface) -> CloseSurface:
    """The channel holds one open incident with its report and its list row."""
    seed_legacy_incident(unseeded.records, CHANNEL_ID, incident_id=INCIDENT_ID, report_url=REPORT_URL)
    return unseeded


def test_close_closes_the_incident_announces_it_and_archives_the_channel(surface: CloseSurface) -> None:
    """The report line, the list cell and the record read Closed; the channel is told, then archived."""
    surface.close()

    assert surface.report_status() == "Closed"
    assert surface.list_status() == "Closed"
    assert surface.stored_status() is IncidentStatus.CLOSED
    # decisions/migration.md step 4 kind (b): decisions/languages.md 2026-11-25 (i18n.md 2026-11-17), a post to a
    # shared conversation is in the instance languages, in order (TASK-145.8.9 named change; legacy: English only).
    assert surface.channel_messages() == [
        f"<@{USER_ID}> has updated the incident status to Closed.\n<@{USER_ID}> a changé le statut de l'incident à Closed.",
        f"<@{USER_ID}> has archived this channel 👋\n<@{USER_ID}> a archivé ce canal 👋",
    ]
    assert surface.archived()


def test_close_with_the_incidents_table_down_archives_nothing(surface: CloseSurface) -> None:
    """A failing record lookup answers that the database is unavailable and leaves the channel and report alone."""
    surface.records.go_down()

    surface.close()

    assert not surface.archived()
    assert surface.report_status() == "Open"
    # Named change (kind b, decisions/i18n.md): the command names the invoker's locale, so the
    # reply is in that language only (the legacy reply was English and French).
    assert surface.replies() == ["The incidents database is temporarily unavailable. Please try again later."]


def test_close_in_a_channel_with_no_incident_closes_and_archives_nothing(unseeded: CloseSurface) -> None:
    """Named change (kind b): a channel with no incident record is refused by the record, not by its name."""
    unseeded.close()

    assert unseeded.replies() == ["This channel is not an incident channel, so there is no incident to close."]
    assert not unseeded.archived()
    assert unseeded.channel_messages() == []
