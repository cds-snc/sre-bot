"""Pinning tests for ``/sre incident status update <status>``, the slash status change.

Each test sends ``/sre incident status ...`` from the incident channel through
``slack_bolt.App.dispatch``, and the provider routes it to the rebuilt
``incident.response`` plugin (TASK-145.8.4). A status change is asserted by what
users see: the report's status line, the status cell of the incident's list
row, the channel message and the invoker's reply, read through ``StatusSurface``
so the assertions name outcomes, never the call shapes that produce them.

The fixture is rewired to the target's fakes (decisions/migration.md step 4):
the plugin's scope opener resolves an in-memory record store holding the
channel's legacy incident, and the response providers return the core
in-memory report, list projection and conversation, seeded as the legacy
edges were (the report and the list row both show Open). The behaviour the
rebuild ended (the record left unwritten, the reply wording, the bare-status
redirect and the ``status show`` stub) was pinned in ``test_legacy_only_*``
tests, deleted with it; the new behaviour is tested under
tests/integration/features/incident/response/.
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
    seed_legacy_incident,
    slack_conversation,
)

from .conftest import CHANNEL_ID, REPORT_DOCUMENT_ID, REPORT_URL, USER_ID, IncidentSurface

pytestmark = pytest.mark.integration

STATUSES = ("In Progress", "Open", "Ready to be Reviewed", "Reviewed", "Closed")
INCIDENT_ID = "inc-1"
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id=REPORT_DOCUMENT_ID)


@dataclass
class StatusSurface:
    """The incident surface read back in domain terms: report status line, list status cell, channel posts, replies."""

    surface: IncidentSurface
    records: SwitchableRecordStore
    reports: InMemoryIncidentReport
    projection: InMemoryIncidentListProjection
    conversations: InMemoryIncidentConversation

    def seed_incident(self) -> None:
        """The channel holds one open incident with its report and its list row."""
        seed_legacy_incident(self.records, CHANNEL_ID, incident_id=INCIDENT_ID, report_url=REPORT_URL)

    def make_store_unavailable(self) -> None:
        """Every later read or write of the incident records fails."""
        self.records.go_down()

    def status(self, text: str) -> None:
        """Send ``/sre incident status <text>`` from the incident channel."""
        self.surface.sre(f"incident status {text}".strip())

    def report_status(self) -> str:
        """The status the report's status line shows."""
        shown = self.reports.status_text_of(REPORT)
        assert shown is not None
        return shown.value

    def list_status(self) -> str:
        """The status cell of the incident's row in the list sheet."""
        [row] = [row for row in self.projection.rows if row[5] == INCIDENT_ID]
        return row[3]

    def channel_messages(self) -> list[str]:
        """The texts posted to the incident channel, in order."""
        return list(self.conversations.posts_in(slack_conversation(CHANNEL_ID)))

    def reply(self) -> str:
        """The one reply the invoker saw."""
        [message] = self.surface.slack.responses
        return str(message["text"])


@pytest.fixture
def status_surface(incident_surface: IncidentSurface, monkeypatch: pytest.MonkeyPatch) -> Iterator[StatusSurface]:
    """The incident surface with the response plugin's commands registered over the core in-memory fakes.

    The report shows Open on its status line and the list holds the incident's
    row with Open, as the legacy edges held them; the channel is open with the
    bot a member. The response catalogue is loaded as the lifespan loads it.
    """
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

    incident_surface.provider.set_scope_opener(
        incident_scopes(records, tenants={WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT})
    )
    plugin.register_slack_commands(registrar=incident_surface.provider)
    load_plugin_catalogues(plugin.register_i18n_resources)
    yield StatusSurface(incident_surface, records, reports, projection, conversations)
    reset_translation_service()


@pytest.mark.parametrize("status", STATUSES)
def test_status_update_moves_the_report_line_the_list_cell_and_tells_the_channel(
    status_surface: StatusSurface, status: str
) -> None:
    """Each of the five statuses rewrites the report's status line and the list cell, and the channel is told who changed it."""
    status_surface.seed_incident()

    status_surface.status(f"update {status}")

    assert status_surface.report_status() == status
    assert status_surface.list_status() == status
    assert status_surface.channel_messages() == [f"<@{USER_ID}> has updated the incident status to {status}."]


def test_status_update_with_an_unknown_status_lists_the_valid_ones_and_changes_nothing(
    status_surface: StatusSurface,
) -> None:
    """A status outside the five is refused with the list of valid statuses; report, list and channel are untouched."""
    status_surface.seed_incident()

    status_surface.status("update Resolved")

    assert status_surface.reply() == (
        "A valid status must be used with this command:\nIn Progress, Open, Ready to be Reviewed, Reviewed, Closed"
    )
    assert (status_surface.report_status(), status_surface.list_status()) == ("Open", "Open")
    assert status_surface.channel_messages() == []


def test_status_update_without_a_status_asks_for_one(status_surface: StatusSurface) -> None:
    """``status update`` alone asks for a status and changes nothing."""
    status_surface.seed_incident()

    status_surface.status("update")

    assert status_surface.reply() == "Please provide a status to update."
    assert status_surface.channel_messages() == []


def test_status_update_outside_an_incident_channel_changes_nothing(status_surface: StatusSurface) -> None:
    """A channel without an incident writes no report line, no list cell and no channel message."""
    status_surface.status("update Closed")

    assert (status_surface.report_status(), status_surface.list_status()) == ("Open", "Open")
    assert status_surface.channel_messages() == []


def test_status_update_with_the_records_unavailable_changes_nothing(status_surface: StatusSurface) -> None:
    """A failing incident store read writes no report line, no list cell and no channel message."""
    status_surface.seed_incident()
    status_surface.make_store_unavailable()

    status_surface.status("update Closed")

    assert (status_surface.report_status(), status_surface.list_status()) == ("Open", "Open")
    assert status_surface.channel_messages() == []
