"""Pinning tests for the incident information modal and its field updates.

Each test sends ``/sre incident show`` through ``slack_bolt.App.dispatch``, presses an
update button of the opened information modal, and submits the field modal that
opens, using the action ids, callback ids, block ids and private metadata read from the
recorded ``views.open`` and ``views.push`` payloads, so no modal-internal id is
hard-coded. The external edges are faked: the Slack Web API, the ``response_url``
post, the incidents table (boto3 DynamoDB client), and the Drive, Docs and Sheets
services. An update is asserted by what Slack shows (the channel message, the
refreshed information modal, and the value a following ``show`` renders) and by the
report status text and the list-sheet row at the Google edges, never by how the
table item is written.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from .conftest import (
    CHANNEL_ID,
    INCIDENT_CHANNEL_NAME,
    REPORT_DOCUMENT_ID,
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

RETRO_URL = "https://docs.google.com/document/d/retro/edit"
STORE_UNAVAILABLE_MESSAGE = (
    "The incidents database is temporarily unavailable. Please try again later.\n"
    "La base de données des incidents est temporairement indisponible. Veuillez réessayer plus tard."
)


@pytest.fixture
def surface(incident_surface: IncidentSurface) -> IncidentSurface:
    """The incident surface holding one open incident, its report document and its list-sheet row."""
    incident_surface.table.seed()
    incident_surface.google.add_incident_report()
    incident_surface.slack.client.replies["users_info"] = {
        "ok": True,
        "user": {"id": USER_ID, "locale": "en-US", "tz": "America/Toronto"},
    }
    return incident_surface


def show(surface: IncidentSurface) -> dict[str, Any]:
    """Run ``/sre incident show`` and return the information modal it opened."""
    surface.sre("incident show")
    return last_view(surface.slack.client)


def shown(view: dict[str, Any], label: str) -> str:
    """The value a section of the information modal shows under ``label``."""
    text = view_text(view)
    return text.split(f"*{label}*:\n", 1)[1].split("\n", 1)[0]


def update_field(surface: IncidentSurface, field: str, answers: dict[str, str | None]) -> None:
    """Press the update button of ``field`` in the shown modal and submit the field modal with ``answers``."""
    info = show(surface)
    surface.slack.interaction(click_payload(info, view_button(info, value=field)))
    [*_, pushed] = surface.slack.client.calls_to("views_push")
    surface.slack.interaction(submission_payload(pushed["view"], answers))


def channel_messages(surface: IncidentSurface) -> list[str]:
    return [call["text"] for call in surface.slack.client.calls_to("chat_postMessage") if call["channel"] == CHANNEL_ID]


# /sre incident show


def test_show_opens_the_information_modal_with_the_incident_and_an_update_button_per_field(surface: IncidentSurface) -> None:
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
    assert shown(view, "Retro Link") == "Unknown"
    for field in ("severity", "status", "detection_time", "start_impact_time", "end_impact_time", "retrospective_url"):
        assert view_button(view, value=field)


def test_show_outside_an_incident_channel_tells_the_invoker_so(incident_surface: IncidentSurface) -> None:
    """A channel without an incident record opens no modal and answers with an explanation."""
    incident_surface.sre("incident show")

    assert incident_surface.slack.client.calls_to("views_open") == []
    [message] = incident_surface.slack.responses
    assert message["text"] == "This command is only available in incident channels. No incident records found for this channel."


def test_show_answers_in_both_languages_when_the_incidents_table_is_down(surface: IncidentSurface) -> None:
    """A failing table read opens no modal and answers with the bilingual unavailable message."""
    surface.table.go_down()

    surface.sre("incident show")

    assert surface.slack.client.calls_to("views_open") == []
    [message] = surface.slack.responses
    assert message["text"] == STORE_UNAVAILABLE_MESSAGE


# update_incident_field and update_field_modal


@pytest.mark.parametrize(
    ("field", "label", "answer"),
    [
        ("severity", "Severity", "sev-1"),
        ("retrospective_url", "Retro Link", RETRO_URL),
    ],
)
def test_updating_a_field_posts_to_the_channel_and_a_following_show_renders_the_new_value(
    surface: IncidentSurface, field: str, label: str, answer: str
) -> None:
    """Submitting the dropdown or text modal announces the change in the channel and the stored value is what ``show`` renders next."""
    block = {"severity": "drop_down_input", "retrospective_url": "plain_text_input"}[field]

    update_field(surface, field, {block: answer})

    assert channel_messages(surface) == [f"<@{USER_ID}> has updated the field {field} to {answer}"]
    assert shown(show(surface), label) == answer


def test_updating_a_field_acks_the_submission_and_refreshes_the_information_modal(surface: IncidentSurface) -> None:
    """The submission acks empty and the root information modal is replaced by one showing the new value."""
    info = show(surface)
    surface.slack.interaction(click_payload(info, view_button(info, value="severity")))
    [pushed] = surface.slack.client.calls_to("views_push")

    response = surface.slack.interaction(submission_payload(pushed["view"], {"drop_down_input": "sev-3"}))

    assert pushed["view_id"] == "V0OPEN"
    assert (response.status, response.body) == (200, "")
    [refreshed] = surface.slack.client.calls_to("views_update")
    assert refreshed["view_id"] == ROOT_VIEW_ID
    assert shown(refreshed["view"], "Severity") == "sev-3"


def test_pressing_update_pushes_a_field_modal_that_starts_on_the_current_value(surface: IncidentSurface) -> None:
    """The update button acks empty and pushes a modal over the information modal, preselecting the stored severity."""
    info = show(surface)

    response = surface.slack.interaction(click_payload(info, view_button(info, value="severity")))

    assert (response.status, response.body) == (200, "")
    [pushed] = surface.slack.client.calls_to("views_push")
    assert pushed["trigger_id"] == "trigger-click"
    [dropdown] = [block["element"] for block in pushed["view"]["blocks"] if block.get("type") == "input"]
    assert dropdown["initial_option"]["value"] == "sev-2"
    assert [option["value"] for option in dropdown["options"]] == ["none", "sev-1", "sev-2", "sev-3", "sev-4"]


def test_updating_a_time_converts_the_users_timezone_to_utc(surface: IncidentSurface) -> None:
    """A time picked as 09:30 in Toronto is announced as picked and stored as 13:30 UTC, which ``show`` renders."""
    update_field(surface, "detection_time", {"date_input": "2026-10-01", "time_input": "09:30"})

    assert channel_messages(surface) == [f"<@{USER_ID}> has updated the field detection_time to 2026-10-01 09:30"]
    stored_epoch = int(datetime(2026, 10, 1, 13, 30, tzinfo=UTC).timestamp())
    assert shown(show(surface), "Detection Time") == f"<!date^{stored_epoch}^{{date}} at {{time}}|Unknown>"


@pytest.mark.parametrize(
    ("field", "label"),
    [("start_impact_time", "Start of Impact"), ("end_impact_time", "End of Impact")],
)
def test_each_impact_time_field_is_updated_independently(surface: IncidentSurface, field: str, label: str) -> None:
    """Updating one impact time leaves the other fields as they were."""
    update_field(surface, field, {"date_input": "2026-10-02", "time_input": "00:15"})

    view = show(surface)
    assert shown(view, label).startswith("<!date^")
    assert [shown(view, other) for other in ("Detection Time", "Severity", "Status")] == ["Unknown", "sev-2", "Open"]


def test_updating_the_status_moves_the_report_the_list_sheet_and_the_shown_value(surface: IncidentSurface) -> None:
    """A status change rewrites the report's status line, the sheet row's status cell and the stored status."""
    update_field(surface, "status", {"drop_down_input": "Ready to be Reviewed"})

    assert "Status: Ready to be Reviewed" in surface.google.docs.texts[REPORT_DOCUMENT_ID]
    assert surface.google.sheet.rows[1][3] == "Ready to be Reviewed"
    assert channel_messages(surface) == [f"<@{USER_ID}> has updated the field status to Ready to be Reviewed"]
    assert shown(show(surface), "Status") == "Ready to be Reviewed"


def test_updating_the_status_tells_the_channel_when_the_sheet_has_no_row_for_it(surface: IncidentSurface) -> None:
    """With no sheet row for the channel the status is still updated and the channel is told the sheet was not."""
    surface.google.sheet.rows = surface.google.sheet.rows[:1]

    update_field(surface, "status", {"drop_down_input": "Reviewed"})

    assert channel_messages(surface) == [
        f"Could not update the incident status in the spreadsheet for channel {INCIDENT_CHANNEL_NAME}.",
        f"<@{USER_ID}> has updated the field status to Reviewed",
    ]
    assert "Status: Reviewed" in surface.google.docs.texts[REPORT_DOCUMENT_ID]
    assert shown(show(surface), "Status") == "Reviewed"
