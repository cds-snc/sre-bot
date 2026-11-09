"""Pinning tests for the retro scheduling modal opened by ``/sre incident schedule``.

The modal's submission (``view_save_event``), its attendee picker (``user_select_action``)
and the success view's link button (``confirm_click``) are modal-internal, so each test
opens the modal with the durable ``/sre incident schedule`` command and reads every id it
sends back from the opened view. The external edges are faked: the Slack Web API (channel
info and members, user profiles, the report bookmark), the Google Calendar free/busy and
event services, and the public holidays API (no holidays). Assertions are on the modal
views, the channel message, the calendar event and its attendees; the slot itself depends
on today's date, so it is asserted by its rules (a weekday, 30 minutes, after the chosen
delay), never by a frozen clock.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import requests

from features.incident.postmortem.settings import get_incident_postmortem_settings

from .conftest import (
    CHANNEL_ID,
    EVENT_LINK,
    INCIDENT_CHANNEL_NAME,
    REPORT_DOCUMENT_ID,
    REPORT_URL,
    TRIGGER_ID,
    USER_ID,
    VIEW_ID,
    IncidentSurface,
    google_http_error,
    last_view,
    submission_payload,
    view_button,
    view_elements,
    view_text,
)

pytestmark = pytest.mark.integration

PEOPLE: dict[str, dict[str, Any]] = {
    USER_ID: {"id": USER_ID, "real_name": "Ivy Invoker", "locale": "en-US", "profile": {"email": "ivy@cds-snc.ca"}},
    "U0ALICE": {"id": "U0ALICE", "real_name": "Alice Martin", "profile": {"email": "alice@cds-snc.ca"}},
    "U0BOB": {"id": "U0BOB", "real_name": "Bob Tremblay", "profile": {"email": "bob@cds-snc.ca"}},
    "U0SRE": {"id": "U0SRE", "real_name": "SRE", "profile": {"email": "sre-bot@cds-snc.ca"}},
}
LOADING_VIEW = {"id": "V0LOADING", "hash": "hash-loading"}


class NoHolidays:
    """The public holidays API's answer for a year without federal holidays."""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"holidays": []}


@pytest.fixture
def surface(incident_surface: IncidentSurface, monkeypatch: pytest.MonkeyPatch) -> IncidentSurface:
    """An incident channel with Alice, Bob and the bot as members; every calendar is free."""
    client = incident_surface.slack.client
    client.replies["conversations_info"] = {
        "ok": True,
        "channel": {"id": CHANNEL_ID, "name": INCIDENT_CHANNEL_NAME, "is_member": True},
    }
    client.replies["bookmarks_list"] = {"ok": True, "bookmarks": [{"title": "Incident report", "link": REPORT_URL}]}
    client.replies["conversations_members"] = {"ok": True, "members": ["U0ALICE", "U0BOB", "U0SRE"]}
    client.replies["users_info"] = lambda **request: {"ok": True, "user": PEOPLE[request["user"]]}
    client.replies["users_lookupByEmail"] = lambda **request: {
        "ok": True,
        "user": next(person for person in PEOPLE.values() if person["profile"]["email"] == request["email"]),
    }
    monkeypatch.setattr(requests, "get", lambda url, **kwargs: NoHolidays())
    return incident_surface


def open_retro_modal(surface: IncidentSurface, text: str = "incident schedule retro") -> dict[str, Any]:
    """Run ``/sre <text>`` in the incident channel and return the modal it opened."""
    surface.sre(text)
    surface.slack.client.replies["views_open"] = {"ok": True, "view": LOADING_VIEW}
    return last_view(surface.slack.client)


def attendee_picker(view: dict[str, Any]) -> dict[str, Any]:
    """The modal's multi-select of channel members."""
    return next(element for element in view_elements(view) if element["type"] == "multi_static_select")


def picker_block_id(view: dict[str, Any]) -> str:
    picker = attendee_picker(view)
    return next(block["block_id"] for block in view["blocks"] if block.get("accessory") is picker)


def options_for(view: dict[str, Any], *names: str) -> list[dict[str, Any]]:
    return [option for option in attendee_picker(view)["options"] if option["text"]["text"] in names]


def select_attendees(surface: IncidentSurface, view: dict[str, Any], *names: str) -> Any:
    """Change the attendee selection in the open modal, as Slack sends the block action."""
    picker = attendee_picker(view)
    return surface.slack.interaction(
        {
            "type": "block_actions",
            "trigger_id": "trigger-select",
            "actions": [
                {"type": picker["type"], "action_id": picker["action_id"], "selected_options": options_for(view, *names)}
            ],
            "view": {
                "id": VIEW_ID,
                "type": "modal",
                "callback_id": view["callback_id"],
                "private_metadata": view["private_metadata"],
                "blocks": view["blocks"],
            },
        }
    )


def submit(surface: IncidentSurface, view: dict[str, Any], days: str, *names: str) -> Any:
    """Submit the modal with a delay in days and the named attendees selected."""
    payload = submission_payload(view, {"number_of_days": days})
    picker = attendee_picker(view)
    payload["view"]["state"]["values"][picker_block_id(view)] = {
        picker["action_id"]: {"type": picker["type"], "selected_options": options_for(view, *names)}
    }
    return surface.slack.interaction(payload)


def view_updates(surface: IncidentSurface) -> list[dict[str, Any]]:
    return surface.slack.client.calls_to("views_update")


@pytest.mark.parametrize("text", ["incident schedule retro", "incident schedule"])
def test_schedule_command_opens_the_retro_modal_listing_the_channel_members(surface: IncidentSurface, text: str) -> None:
    """``/sre incident schedule`` (retro is the default) opens the modal with every member but the bot to pick from."""
    view = open_retro_modal(surface, text)

    assert surface.slack.client.calls_to("views_open")[0]["trigger_id"] == TRIGGER_ID
    assert view["title"]["text"] == "SRE - Schedule Retro 🗓️"
    assert [option["text"]["text"] for option in attendee_picker(view)["options"]] == ["Alice Martin", "Bob Tremblay"]


def test_schedule_command_outside_an_incident_channel_says_so_and_opens_nothing(surface: IncidentSurface) -> None:
    """In a channel not named incident-*, the channel gets a notice and no modal opens."""
    surface.slack.client.replies["conversations_info"] = {"ok": True, "channel": {"id": CHANNEL_ID, "name": "general"}}

    surface.sre("incident schedule retro", channel_name="general")

    assert surface.slack.client.calls_to("views_open") == []
    assert surface.slack.client.calls_to("chat_postMessage")[-1] == {
        "channel": CHANNEL_ID,
        "text": "This channel is not an incident channel. Please use this command in an incident channel.",
    }


def test_selecting_an_attendee_with_a_fully_booked_calendar_warns_in_the_modal(surface: IncidentSurface) -> None:
    """Picking attendees checks their calendars; one busy over the whole range is named in a warning."""
    view = open_retro_modal(surface)
    surface.google.calendar.fully_busy = {"bob@cds-snc.ca"}

    response = select_attendees(surface, view, "Alice Martin", "Bob Tremblay")

    assert response.status == 200
    update = view_updates(surface)[-1]
    assert update["view_id"] == VIEW_ID
    assert "calendar availability issues" in view_text(update["view"])
    assert "<@U0BOB>" in view_text(update["view"])
    assert "<@U0ALICE>" not in view_text(update["view"])
    assert [item["id"] for item in surface.google.calendar.queries[-1]["items"]] == ["alice@cds-snc.ca", "bob@cds-snc.ca"]


def test_clearing_the_attendees_redraws_the_modal_without_a_warning(surface: IncidentSurface) -> None:
    """An empty selection redraws the same options with no calendar lookup."""
    view = open_retro_modal(surface)

    select_attendees(surface, view)

    update = view_updates(surface)[-1]
    assert "calendar availability issues" not in view_text(update["view"])
    assert attendee_picker(update["view"])["options"] == attendee_picker(view)["options"]
    assert surface.google.calendar.queries == []


def test_submitting_books_one_retro_event_with_the_selected_attendees(surface: IncidentSurface) -> None:
    """Submitting books the first free 30-minute weekday slot after the delay and announces it in the channel."""
    view = open_retro_modal(surface)
    earliest = datetime.now(UTC).date() + timedelta(days=3)

    response = submit(surface, view, "3", "Alice Martin", "Bob Tremblay")

    assert response.status == 200
    [event] = surface.google.calendar.events
    body = event["body"]
    assert event["calendarId"] == get_incident_postmortem_settings().calendar_id
    assert body["summary"] == f"Retro {INCIDENT_CHANNEL_NAME}"
    assert [attendee["email"] for attendee in body["attendees"]] == ["alice@cds-snc.ca", "bob@cds-snc.ca"]
    assert body["attachments"][0]["fileUrl"] == f"https://docs.google.com/document/d/{REPORT_DOCUMENT_ID}"
    start = datetime.fromisoformat(body["start"]["dateTime"])
    end = datetime.fromisoformat(body["end"]["dateTime"])
    assert end - start == timedelta(minutes=30)
    assert start.weekday() < 5
    assert start.astimezone(UTC).date() >= earliest
    announcement = surface.slack.client.calls_to("chat_postMessage")[-1]
    assert announcement["channel"] == CHANNEL_ID
    assert announcement["text"].startswith("Retro has been scheduled for ")
    loading, done = surface.slack.client.calls_to("views_open")[-1], view_updates(surface)[-1]
    assert "Scheduling the retro" in view_text(loading["view"])
    assert (done["view_id"], done["hash"]) == (LOADING_VIEW["id"], LOADING_VIEW["hash"])
    assert view_button(done["view"], value="view_event")["url"] == EVENT_LINK


def test_confirm_click_on_the_event_link_is_acknowledged_without_any_call(surface: IncidentSurface) -> None:
    """Opening the booked event from the success view only acknowledges the click."""
    submit(surface, open_retro_modal(surface), "3", "Alice Martin")
    button = view_button(view_updates(surface)[-1]["view"], value="view_event")
    calls_before = len(surface.slack.client.calls)

    response = surface.slack.interaction(
        {
            "type": "block_actions",
            "user": {"id": USER_ID, "username": "ivy"},
            "trigger_id": "trigger-click",
            "actions": [{"type": "button", "action_id": button["action_id"], "value": button["value"]}],
            "view": {"id": LOADING_VIEW["id"], "type": "modal", "callback_id": "", "private_metadata": ""},
        }
    )

    assert response.status == 200
    assert len(surface.slack.client.calls) == calls_before


def test_submitting_when_every_attendee_is_booked_shows_the_no_free_time_view(surface: IncidentSurface) -> None:
    """With no free slot in the search window, nothing is booked and the modal says so."""
    view = open_retro_modal(surface)
    surface.google.calendar.fully_busy = {"alice@cds-snc.ca"}

    submit(surface, view, "3", "Alice Martin")

    assert surface.google.calendar.events == []
    assert "no free time was found" in view_text(view_updates(surface)[-1]["view"])
    assert surface.slack.client.calls_to("chat_postMessage") == []


def test_submitting_when_the_calendar_refuses_the_event_leaves_the_loading_view(surface: IncidentSurface) -> None:
    """A refused booking escapes the handler: the modal stays on the loading view and the channel hears nothing.

    The handler acknowledges before it books, so Slack sees the ack; the response is not
    asserted because the harness runs listeners inline, where Bolt's error path clears that
    ack and waits out its 3-second ack timeout before answering "unhandled".
    """
    view = open_retro_modal(surface)
    surface.google.calendar.insert_error = google_http_error(403, "Calendar access denied")

    submit(surface, view, "3", "Alice Martin")

    assert surface.google.calendar.events == []
    assert view_updates(surface) == []
    assert surface.slack.client.calls_to("chat_postMessage") == []
