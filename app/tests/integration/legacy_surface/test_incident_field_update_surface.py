"""Pinning tests for the incident information modal and its field updates.

Each test sends ``/sre incident show`` through ``slack_bolt.App.dispatch``, and the
provider routes it to the rebuilt ``incident.response`` plugin (TASK-145.8.3). It presses
an update button of the opened information modal and submits the field modal that opens,
using the action ids, callback ids, block ids and private metadata read from the recorded
``views.open`` and ``views.push`` payloads, so no modal-internal id is hard-coded. An
update is asserted by what Slack shows (the channel message, the refreshed information
modal, and the value a following ``show`` renders) and by the report status line and the
list row's status cell, read through ``FieldSurface`` in domain terms.

The fixture is rewired to the target's fakes (decisions/migration.md step 4): the plugin's
scope opener resolves an in-memory record store holding the channel's legacy incident, and
the response providers return the core in-memory report, list projection, conversation,
video call and legacy roles reader, seeded as the legacy edges were (the report and the
list row both show Open). The behaviour the rebuild ended (the Retro Link, the report and
sheet written before the record, the public spreadsheet notice) was pinned in
``test_legacy_only_*`` tests, deleted with it. Edited assertions cite the named changes of
TASK-145.8.3's plan: N8 (views.push sends no view id), N10 (the unavailable reply in the
invoker's locale), N13 (one date-and-time picker; the notice names the instant with a Slack
date token) and N14 (the channel notice in English and French). The new behaviour is
tested under tests/unit/features/incident/response/.
"""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
    InMemoryLegacyRolesReader,
    InMemoryVideoCall,
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

from .conftest import (
    CHANNEL_ID,
    REPORT_DOCUMENT_ID,
    REPORT_URL,
    ROOT_VIEW_ID,
    USER_ID,
    IncidentSurface,
    click_payload,
    last_view,
    submission_payload,
    view_button,
    view_text,
)

pytestmark = pytest.mark.integration

INCIDENT_ID = "inc-1"
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id=REPORT_DOCUMENT_ID)
# N10: a command answers in the invoker's locale only (decisions/i18n.md Locale resolution).
STORE_UNAVAILABLE_MESSAGE = "The incidents database is temporarily unavailable. Please try again later."


def notice(field: str, value: str) -> str:
    """The channel notice of a field change. N14: a shared conversation is written in English and French."""
    return f"<@{USER_ID}> has updated the field {field} to {value}\n<@{USER_ID}> a mis à jour le champ {field} à {value}"


@dataclass
class FieldSurface:
    """The incident surface read back in domain terms: report status line, list status cell, channel posts."""

    surface: IncidentSurface
    records: SwitchableRecordStore
    reports: InMemoryIncidentReport
    projection: InMemoryIncidentListProjection
    conversations: InMemoryIncidentConversation

    @property
    def slack(self) -> Any:
        return self.surface.slack

    def sre(self, text: str) -> Any:
        return self.surface.sre(text)

    def report_status(self) -> str:
        """The status the report's status line shows."""
        shown = self.reports.status_text_of(REPORT)
        assert shown is not None
        return shown.value

    def list_status(self) -> str:
        """The status cell of the incident's row in the list sheet."""
        [row] = [row for row in self.projection.rows if row[5] == INCIDENT_ID]
        return row[3]


@pytest.fixture
def unseeded(incident_surface: IncidentSurface, monkeypatch: pytest.MonkeyPatch) -> Iterator[FieldSurface]:
    """The incident surface with the response plugin registered over the core in-memory fakes, no incident yet.

    The report shows Open on its status line and the list holds the incident's row with Open,
    as the legacy edges held them; the channel is open with the bot a member. The response
    catalogue is loaded as the lifespan loads it.
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
    monkeypatch.setattr(providers, "legacy_roles_reader", InMemoryLegacyRolesReader)
    monkeypatch.setattr(providers, "video_call", InMemoryVideoCall)

    incident_surface.provider.set_scope_opener(
        incident_scopes(records, tenants={WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT})
    )
    plugin.register_slack_commands(registrar=incident_surface.provider)
    incident_surface.provider._attach_interaction_listeners()  # the Bolt app is built before the plugin registers
    load_plugin_catalogues(plugin.register_i18n_resources)
    yield FieldSurface(incident_surface, records, reports, projection, conversations)
    reset_translation_service()


@pytest.fixture
def surface(unseeded: FieldSurface) -> FieldSurface:
    """The surface holding one open incident, its report and its list row."""
    seed_legacy_incident(
        unseeded.records,
        CHANNEL_ID,
        incident_id=INCIDENT_ID,
        report_url=REPORT_URL,
        name="Checkout outage",
        severity="sev-2",
        meet_url="https://meet.google.com/abc-defg-hij",
    )
    return unseeded


def show(surface: FieldSurface) -> dict[str, Any]:
    """Run ``/sre incident show`` and return the information modal it opened."""
    surface.sre("incident show")
    return last_view(surface.slack.client)


def shown(view: dict[str, Any], label: str) -> str:
    """The value a section of the information modal shows under ``label``."""
    text = view_text(view)
    return text.split(f"*{label}*:\n", 1)[1].split("\n", 1)[0]


def update_field(surface: FieldSurface, field: str, answers: dict[str, str | int | None]) -> None:
    """Press the update button of ``field`` in the shown modal and submit the field modal with ``answers``."""
    info = show(surface)
    surface.slack.interaction(click_payload(info, view_button(info, value=field)))
    [*_, pushed] = surface.slack.client.calls_to("views_push")
    surface.slack.interaction(submission_payload(pushed["view"], answers))


def channel_messages(surface: FieldSurface) -> list[str]:
    return list(surface.conversations.posts_in(slack_conversation(CHANNEL_ID)))


def instant(year: int, month: int, day: int, hour: int, minute: int) -> int:
    """The UNIX seconds the date-and-time picker returns for a UTC instant (N13)."""
    return int(datetime(year, month, day, hour, minute, tzinfo=UTC).timestamp())


# /sre incident show


def test_show_opens_the_information_modal_with_the_incident_and_an_update_button_per_field(surface: FieldSurface) -> None:
    """The command acks empty and opens a modal naming the incident, its report and meet links and its current values."""
    response = surface.sre("incident show")

    assert (response.status, response.body) == (200, "")
    view = last_view(surface.slack.client)
    assert view["blocks"][0]["text"]["text"] == "Checkout outage"
    text = view_text(view)
    assert "*ID*: inc-1" in text
    assert "<https://docs.google.com/document/d/doc-source/edit|:memo: Incident Report>" in text
    assert "<https://meet.google.com/abc-defg-hij|:headphones: Google Meet>" in text
    assert (shown(view, "Severity"), shown(view, "Status")) == ("sev-2", "Open")
    assert (shown(view, "Detection Time"), shown(view, "Start of Impact"), shown(view, "End of Impact")) == ("Unknown",) * 3
    for field in ("severity", "status", "detection_time", "start_impact_time", "end_impact_time"):
        assert view_button(view, value=field)


def test_show_outside_an_incident_channel_tells_the_invoker_so(unseeded: FieldSurface) -> None:
    """A channel without an incident record opens no modal and answers with an explanation."""
    unseeded.sre("incident show")

    assert unseeded.slack.client.calls_to("views_open") == []
    [message] = unseeded.slack.responses
    assert message["text"] == "This command is only available in incident channels. No incident records found for this channel."


def test_show_answers_in_the_invokers_language_when_the_incidents_table_is_down(surface: FieldSurface) -> None:
    """A failing table read opens no modal and answers with the unavailable message (N10: in the invoker's locale)."""
    surface.records.go_down()

    surface.sre("incident show")

    assert surface.slack.client.calls_to("views_open") == []
    [message] = surface.slack.responses
    assert message["text"] == STORE_UNAVAILABLE_MESSAGE


# The update buttons and the field modal


def test_updating_a_field_posts_to_the_channel_and_a_following_show_renders_the_new_value(surface: FieldSurface) -> None:
    """Submitting the severity modal announces the change in the channel and the stored value is what ``show`` renders next."""
    update_field(surface, "severity", {"drop_down_input": "sev-1"})

    assert channel_messages(surface) == [notice("severity", "sev-1")]
    assert shown(show(surface), "Severity") == "sev-1"


def test_updating_a_field_acks_the_submission_and_refreshes_the_information_modal(surface: FieldSurface) -> None:
    """The submission acks empty and the root information modal is replaced by one showing the new value.

    N8: views.push no longer sends a view id, which views.push does not define, so the
    pushed call's ``view_id`` is not asserted.
    """
    info = show(surface)
    surface.slack.interaction(click_payload(info, view_button(info, value="severity")))
    [pushed] = surface.slack.client.calls_to("views_push")

    response = surface.slack.interaction(submission_payload(pushed["view"], {"drop_down_input": "sev-3"}))

    assert (response.status, response.body) == (200, "")
    [refreshed] = surface.slack.client.calls_to("views_update")
    assert refreshed["view_id"] == ROOT_VIEW_ID
    assert shown(refreshed["view"], "Severity") == "sev-3"


def test_pressing_update_pushes_a_field_modal_that_starts_on_the_current_value(surface: FieldSurface) -> None:
    """The update button acks empty and pushes a modal over the information modal, preselecting the stored severity.

    SEV0 is offered first after none (the declare cutover's named change N4).
    """
    info = show(surface)

    response = surface.slack.interaction(click_payload(info, view_button(info, value="severity")))

    assert (response.status, response.body) == (200, "")
    [pushed] = surface.slack.client.calls_to("views_push")
    assert pushed["trigger_id"] == "trigger-click"
    [dropdown] = [block["element"] for block in pushed["view"]["blocks"] if block.get("type") == "input"]
    assert dropdown["initial_option"]["value"] == "sev-2"
    assert [option["value"] for option in dropdown["options"]] == ["none", "sev-0", "sev-1", "sev-2", "sev-3", "sev-4"]


def test_updating_a_time_stores_the_picked_instant(surface: FieldSurface) -> None:
    """A time picked as 09:30 in Toronto (13:30 UTC) is announced as that instant and stored, which ``show`` renders.

    N13: one date-and-time picker returns the instant itself, so no time zone is looked up and
    the notice names the instant with a Slack date token, which each reader sees in their own zone.
    """
    picked = instant(2026, 10, 1, 13, 30)

    update_field(surface, "detection_time", {"date_time_input": picked})

    when = f"<!date^{picked}^{{date_num}} {{time}}|2026-10-01T13:30:00+00:00>"
    assert channel_messages(surface) == [notice("detection_time", when)]
    assert shown(show(surface), "Detection Time") == f"<!date^{picked}^{{date}} at {{time}}|Unknown>"


@pytest.mark.parametrize(
    ("field", "label"),
    [("start_impact_time", "Start of Impact"), ("end_impact_time", "End of Impact")],
)
def test_each_impact_time_field_is_updated_independently(surface: FieldSurface, field: str, label: str) -> None:
    """Updating one impact time leaves the other fields as they were."""
    update_field(surface, field, {"date_time_input": instant(2026, 10, 2, 4, 15)})

    view = show(surface)
    assert shown(view, label).startswith("<!date^")
    assert [shown(view, other) for other in ("Detection Time", "Severity", "Status")] == ["Unknown", "sev-2", "Open"]


def test_updating_the_status_moves_the_report_the_list_sheet_and_the_shown_value(surface: FieldSurface) -> None:
    """A status change rewrites the report's status line, the list row's status cell and the stored status."""
    update_field(surface, "status", {"drop_down_input": "Ready to be Reviewed"})

    assert surface.report_status() == "Ready to be Reviewed"
    assert surface.list_status() == "Ready to be Reviewed"
    assert channel_messages(surface) == [notice("status", "Ready to be Reviewed")]
    assert shown(show(surface), "Status") == "Ready to be Reviewed"
