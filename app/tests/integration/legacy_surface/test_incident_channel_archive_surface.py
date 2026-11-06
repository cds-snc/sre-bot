"""Pinning tests for the ``archive_channel`` buttons on the stale incident channel notice.

The notice posted by the stale-channel job carries the callback id ``archive_channel``
and three buttons (``archive``, ``schedule_retro``, ``ignore``). That id is on a message
already posted in channels, so each test presses a button by sending the
``interactive_message`` payload Slack would send through ``slack_bolt.App.dispatch``.
The external edges are faked: the Slack Web API, the ``response_url`` post, Sentinel,
the incidents table (boto3 DynamoDB client), and the Drive, Docs and Sheets services.
Assertions are on the Slack calls (notice rewritten, messages posted, channel archived,
retro modal opened), the Sentinel events, the report status text and sheet row, and the
status a following ``/sre incident show`` renders; never on how the table is written.
"""

from typing import Any

import pytest

from .conftest import (
    CHANNEL_ID,
    INCIDENT_CHANNEL_NAME,
    REPORT_DOCUMENT_ID,
    REPORT_URL,
    RESPONSE_URL,
    USER_ID,
    IncidentSurface,
    last_view,
    view_text,
)

pytestmark = pytest.mark.integration

NOTICE_TS = "1700000000.000200"
STORE_UNAVAILABLE_MESSAGE = (
    "The incidents database is temporarily unavailable. Please try again later.\n"
    "La base de données des incidents est temporairement indisponible. Veuillez réessayer plus tard."
)


@pytest.fixture
def surface(incident_surface: IncidentSurface) -> IncidentSurface:
    """The incident surface for an open incident whose channel the bot is already a member of."""
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
    return incident_surface


def press(surface: IncidentSurface, button: str, channel_name: str = INCIDENT_CHANNEL_NAME) -> Any:
    """Press ``button`` on the stale-channel notice, as Slack sends an interactive message action."""
    return surface.slack.interaction(
        {
            "type": "interactive_message",
            "callback_id": "archive_channel",
            "actions": [{"name": button, "type": "button", "value": button}],
            "channel": {"id": CHANNEL_ID, "name": channel_name},
            "message_ts": NOTICE_TS,
            "trigger_id": "trigger-notice",
            "response_url": RESPONSE_URL,
            "original_message": {
                "text": "This channel has been quiet for 14 days",
                "attachments": [{"callback_id": "archive_channel"}],
            },
        }
    )


def sentinel_events(surface: IncidentSurface) -> list[str]:
    return [event["event"] for event in surface.slack.sentinel_events]


def posted_texts(surface: IncidentSurface) -> list[str]:
    return [call["text"] for call in surface.slack.client.calls_to("chat_postMessage") if call["channel"] == CHANNEL_ID]


def shown_status(surface: IncidentSurface) -> str:
    surface.sre("incident show")
    return view_text(last_view(surface.slack.client)).split("*Status*:\n", 1)[1].split("\n", 1)[0]


# ignore


def test_ignore_rewrites_the_notice_without_buttons_and_records_one_sentinel_event(surface: IncidentSurface) -> None:
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


def test_archive_closes_the_incident_in_the_report_the_sheet_and_the_record(surface: IncidentSurface) -> None:
    """Archiving moves the report's status line, the sheet row and the incident's status to Closed."""
    press(surface, "archive")

    assert "Status: Closed" in surface.google.docs.texts[REPORT_DOCUMENT_ID]
    assert surface.google.sheet.rows[1][3] == "Closed"
    assert shown_status(surface) == "Closed"


def test_archive_announces_the_close_then_archives_the_channel(surface: IncidentSurface) -> None:
    """The channel is told who closed the incident and who archived the channel, before Slack archives it."""
    response = press(surface, "archive")

    assert (response.status, response.body) == (200, "")
    assert posted_texts(surface) == [
        f"<@{USER_ID}> has updated the incident status to Closed.",
        f"<@{USER_ID}> has archived this channel 👋",
    ]
    assert surface.slack.client.calls_to("conversations_archive") == [{"channel": CHANNEL_ID}]
    assert surface.slack.client.calls_to("chat_update") == []


def test_archive_records_the_archive_in_sentinel(surface: IncidentSurface) -> None:
    """Archiving emits incident_channel_archived and no other event kind."""
    press(surface, "archive")

    assert set(sentinel_events(surface)) == {"incident_channel_archived"}


def test_archive_joins_the_channel_first_when_the_bot_is_not_a_member(surface: IncidentSurface) -> None:
    """A channel the bot has not joined is joined before the status update and the archive."""
    surface.slack.client.replies["conversations_info"] = {
        "ok": True,
        "channel": {"name": INCIDENT_CHANNEL_NAME, "is_member": False},
    }

    press(surface, "archive")

    assert surface.slack.client.calls_to("conversations_join") == [{"channel": CHANNEL_ID}]
    assert surface.slack.client.calls_to("conversations_archive") == [{"channel": CHANNEL_ID}]


def test_archive_refuses_a_channel_that_is_not_an_incident_channel(surface: IncidentSurface) -> None:
    """In a channel not named incident-* nothing is closed or archived and the presser gets an ephemeral refusal."""
    press(surface, "archive", channel_name="general")

    assert surface.slack.client.calls_to("chat_postEphemeral") == [
        {
            "text": "Channel general is not an incident channel. Please use this command in an incident channel.",
            "channel": CHANNEL_ID,
            "user": USER_ID,
        }
    ]
    assert surface.slack.client.calls_to("conversations_archive") == []
    assert posted_texts(surface) == []
    assert "Status: Open" in surface.google.docs.texts[REPORT_DOCUMENT_ID]


def test_archive_answers_in_both_languages_and_archives_nothing_when_the_incidents_table_is_down(
    surface: IncidentSurface,
) -> None:
    """A failing record lookup answers with the bilingual unavailable message and leaves the channel and report alone."""
    surface.table.go_down()

    press(surface, "archive")

    [message] = surface.slack.responses
    assert message["text"] == STORE_UNAVAILABLE_MESSAGE
    assert surface.slack.client.calls_to("conversations_archive") == []
    assert "Status: Open" in surface.google.docs.texts[REPORT_DOCUMENT_ID]


# schedule_retro


def test_schedule_retro_opens_the_retro_modal_and_records_one_sentinel_event(surface: IncidentSurface) -> None:
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
