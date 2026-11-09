"""Pinning tests for the floppy-disk reaction events that capture incident timeline entries.

``reaction_added`` and ``reaction_removed`` are each registered twice: a listener behind
the ``is_floppy_disk`` matcher, then an ack-only fallback for every other emoji. The event
types are the durable entry points, so each test sends the Events API callback Slack would
send through ``slack_bolt.App.dispatch``. The external edges are faked: the Slack Web API
(channel info, the reacted message, its permalink, the author's profile, the channel
bookmark to the report) and the Docs service holding the incident report. Assertions are
on the report's timeline section as a reader of the document sees it (linked times written
``[time](url)``) and on the Web API calls; never on how the section edit is computed.
"""

from typing import Any

import pytest

from .conftest import (
    CHANNEL_ID,
    INCIDENT_CHANNEL_NAME,
    REPORT_DOCUMENT_ID,
    REPORT_URL,
    TIMELINE_PLACEHOLDER,
    USER_ID,
    IncidentSurface,
)

pytestmark = pytest.mark.integration

AUTHOR_ID = "U0AUTHOR"
ROLLBACK = {"ts": "1760000300.000100", "user": AUTHOR_ID, "text": "Rolled back the deploy"}
ALERT = {"ts": "1760000000.000100", "user": AUTHOR_ID, "text": "Error rate alert fired"}
ROLLBACK_ENTRY = (
    " ➡️ [2025-10-09 04:58:20 ET](https://cds.slack.com/archives/C0INCIDENT/p1760000300000100) Jane Doe: Rolled back the deploy\n"
)
ALERT_ENTRY = (
    " ➡️ [2025-10-09 04:53:20 ET](https://cds.slack.com/archives/C0INCIDENT/p1760000000000100) Jane Doe: Error rate alert fired\n"
)


def permalink(ts: str) -> str:
    return f"https://cds.slack.com/archives/{CHANNEL_ID}/p{ts.replace('.', '')}"


@pytest.fixture
def surface(incident_surface: IncidentSurface) -> IncidentSurface:
    """An incident channel whose report has an empty timeline, with two messages posted by Jane Doe."""
    incident_surface.google.add_timeline_report()
    client = incident_surface.slack.client
    client.replies["conversations_info"] = {"ok": True, "channel": {"id": CHANNEL_ID, "name": INCIDENT_CHANNEL_NAME}}
    client.replies["bookmarks_list"] = {"ok": True, "bookmarks": [{"title": "Incident report", "link": REPORT_URL}]}
    client.replies["users_profile_get"] = {"ok": True, "profile": {"real_name": "Jane Doe", "display_name": "jane"}}
    messages = {message["ts"]: message for message in (ROLLBACK, ALERT)}
    client.replies["conversations_history"] = lambda **request: {
        "ok": True,
        "messages": [dict(messages[request["ts"]])],
        "has_more": False,
    }
    client.replies["chat_getPermalink"] = lambda **request: {"ok": True, "permalink": permalink(request["message_ts"])}
    return incident_surface


def react(surface: IncidentSurface, event_type: str, message: dict[str, str], reaction: str = "floppy_disk") -> Any:
    """Send the ``reaction_added`` or ``reaction_removed`` callback for ``reaction`` on ``message``."""
    return surface.slack.event(
        {
            "type": event_type,
            "user": USER_ID,
            "reaction": reaction,
            "item_user": message["user"],
            "item": {"type": "message", "channel": CHANNEL_ID, "ts": message["ts"]},
            "event_ts": "1760000400.000100",
        }
    )


def timeline(surface: IncidentSurface) -> str:
    """The report text between the timeline placeholder line and the ``Trigger`` heading."""
    report = surface.google.docs.linked_text(REPORT_DOCUMENT_ID)
    return report.split(f"{TIMELINE_PLACEHOLDER}\n", 1)[1].split("Trigger\n", 1)[0]


def test_floppy_disk_reaction_appends_the_message_to_the_report_timeline(surface: IncidentSurface) -> None:
    """A floppy disk on a message in an incident channel adds one linked, attributed entry to the timeline."""
    response = react(surface, "reaction_added", ROLLBACK)

    assert response.status == 200
    assert timeline(surface) == "\n" + ROLLBACK_ENTRY


def test_floppy_disk_reactions_keep_the_timeline_in_chronological_order(surface: IncidentSurface) -> None:
    """Saving a later message first and an earlier one second still lists them oldest first."""
    react(surface, "reaction_added", ROLLBACK)
    react(surface, "reaction_added", ALERT)

    assert timeline(surface) == "\n" + ALERT_ENTRY + ROLLBACK_ENTRY


def test_floppy_disk_reaction_on_a_saved_message_leaves_the_report_unchanged(surface: IncidentSurface) -> None:
    """A second floppy disk on a message already in the timeline writes nothing to the report."""
    react(surface, "reaction_added", ROLLBACK)
    react(surface, "reaction_added", ROLLBACK)

    assert timeline(surface) == "\n" + ROLLBACK_ENTRY
    assert len(surface.google.docs.edits) == 1


def test_floppy_disk_reaction_retries_when_the_report_changed_underneath(surface: IncidentSurface) -> None:
    """A write refused because someone else edited the report is redone from a fresh read, once."""
    surface.google.docs.concurrent_edits = 1

    react(surface, "reaction_added", ROLLBACK)

    assert timeline(surface) == "\n" + ROLLBACK_ENTRY
    assert len(surface.google.docs.edits) == 2


def test_floppy_disk_removal_deletes_the_message_from_the_timeline(surface: IncidentSurface) -> None:
    """Removing the floppy disk takes that message's entry out and keeps the others."""
    react(surface, "reaction_added", ALERT)
    react(surface, "reaction_added", ROLLBACK)

    response = react(surface, "reaction_removed", ROLLBACK)

    assert response.status == 200
    assert timeline(surface) == "\n" + ALERT_ENTRY


def test_floppy_disk_removal_of_an_unsaved_message_leaves_the_report_unchanged(surface: IncidentSurface) -> None:
    """Removing a floppy disk from a message that is not in the timeline writes nothing."""
    react(surface, "reaction_added", ALERT)

    react(surface, "reaction_removed", ROLLBACK)

    assert timeline(surface) == "\n" + ALERT_ENTRY
    assert len(surface.google.docs.edits) == 1


@pytest.mark.parametrize("event_type", ["reaction_added", "reaction_removed"])
def test_floppy_disk_reaction_outside_an_incident_channel_only_reads_the_channel(
    surface: IncidentSurface, event_type: str
) -> None:
    """In a channel not named incident-*, the reaction is acknowledged after one channel lookup and nothing else."""
    surface.slack.client.replies["conversations_info"] = {"ok": True, "channel": {"id": CHANNEL_ID, "name": "general"}}

    response = react(surface, event_type, ROLLBACK)

    assert response.status == 200
    assert [name for name, _ in surface.slack.client.calls] == ["conversations_info"]
    assert surface.google.docs.edits == []


@pytest.mark.parametrize("event_type", ["reaction_added", "reaction_removed"])
def test_other_reaction_is_acknowledged_without_any_call(surface: IncidentSurface, event_type: str) -> None:
    """Any other emoji reaches only the ack-only fallback: no Web API call and no report edit."""
    response = react(surface, event_type, ROLLBACK, reaction="white_check_mark")

    assert response.status == 200
    assert surface.slack.client.calls == []
    assert surface.google.docs.edits == []
