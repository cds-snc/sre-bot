"""Pins what the daily stale incident channel job does on the Slack Web API.

The job entry point is called directly. The Slack Web API is faked at
``WebClient.api_call`` with per-channel history and per-cursor channel pages,
and the Sentinel sender is recorded. Assertions are on the messages posted,
the channels joined and the Sentinel events, never on logging or helpers.
"""

import time
from typing import Any

import pytest

from jobs.scheduled_tasks import notify_stale_incident_channels_job as run_stale_channel_job
from tests.integration.legacy_surface.conftest import RoutedSlackEdges

pytestmark = pytest.mark.integration

DAY = 24 * 60 * 60
USER_MESSAGE = {"type": "message", "text": "still working on it", "team": "T0TEAM", "user": "U0USER"}
BOT_MESSAGE = {"type": "message", "subtype": "bot_message", "text": "reminder", "bot_id": "B0BOT"}


def channel(channel_id: str, name: str, age_days: float) -> dict[str, Any]:
    return {"id": channel_id, "name": name, "created": time.time() - age_days * DAY}


def history(*messages: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "messages": list(messages)}


def posted_channels(edges: RoutedSlackEdges) -> list[str]:
    return [call["channel"] for call in edges.client.calls_to("chat_postMessage")]


def test_quiet_old_incident_channel_gets_one_bilingual_notice_with_three_buttons(routed_slack_client: RoutedSlackEdges) -> None:
    """A channel past 14 days with no user message is nudged once with the archive, retro and ignore buttons."""
    stale = channel("C0STALE", "incident-2025-01-widgets", age_days=20)
    routed_slack_client.client.channel_pages = {None: {"ok": True, "channels": [stale]}}

    run_stale_channel_job()

    posts = routed_slack_client.client.calls_to("chat_postMessage")
    assert len(posts) == 1
    assert posts[0]["channel"] == "C0STALE"
    assert "14 days" in posts[0]["text"]
    assert "14 jours" in posts[0]["text"]
    (attachment,) = posts[0]["attachments"]
    assert attachment["callback_id"] == "archive_channel"
    assert [action["name"] for action in attachment["actions"]] == ["archive", "schedule_retro", "ignore"]


def test_nudge_is_recorded_as_a_sentinel_event_naming_the_channel(routed_slack_client: RoutedSlackEdges) -> None:
    """Each nudge emits sent_stale_channel_notification carrying the nudged channel."""
    stale = channel("C0STALE", "incident-2025-01-widgets", age_days=20)
    routed_slack_client.client.channel_pages = {None: {"ok": True, "channels": [stale]}}

    run_stale_channel_job()

    assert len(routed_slack_client.sentinel_events) == 1
    event = routed_slack_client.sentinel_events[0]
    assert event["event"] == "sent_stale_channel_notification"
    assert event["message"]["channel"]["id"] == "C0STALE"
    assert event["message"]["channel"]["name"] == "incident-2025-01-widgets"


def test_channels_that_are_not_incident_channels_are_never_joined_or_posted_to(routed_slack_client: RoutedSlackEdges) -> None:
    """Old quiet channels whose name does not match incident-NNNN- are left alone."""
    routed_slack_client.client.channel_pages = {
        None: {
            "ok": True,
            "channels": [
                channel("C0GENERAL", "general", age_days=90),
                channel("C0SHORT", "incident-12-short", age_days=90),
                channel("C0TALK", "chat-incident-2025-01", age_days=90),
            ],
        }
    }

    run_stale_channel_job()

    assert routed_slack_client.client.calls_to("conversations_join") == []
    assert posted_channels(routed_slack_client) == []
    assert routed_slack_client.sentinel_events == []


def test_incident_channel_younger_than_fourteen_days_is_not_nudged(routed_slack_client: RoutedSlackEdges) -> None:
    """A quiet incident channel created 3 days ago is not stale yet."""
    routed_slack_client.client.channel_pages = {
        None: {"ok": True, "channels": [channel("C0NEW", "incident-2025-02-fresh", age_days=3)]}
    }

    run_stale_channel_job()

    assert posted_channels(routed_slack_client) == []


def test_incident_channel_with_a_recent_user_message_is_not_nudged(routed_slack_client: RoutedSlackEdges) -> None:
    """A user message in the 14-day window keeps an old channel from being nudged."""
    routed_slack_client.client.channel_pages = {
        None: {"ok": True, "channels": [channel("C0BUSY", "incident-2025-01-busy", age_days=30)]}
    }
    routed_slack_client.client.history_by_channel["C0BUSY"] = history(BOT_MESSAGE, USER_MESSAGE)

    run_stale_channel_job()

    assert posted_channels(routed_slack_client) == []
    assert routed_slack_client.sentinel_events == []


def test_window_holding_only_bot_messages_still_counts_as_stale(routed_slack_client: RoutedSlackEdges) -> None:
    """Messages without a team key are not user activity, so the channel is nudged."""
    routed_slack_client.client.channel_pages = {
        None: {"ok": True, "channels": [channel("C0BOTS", "incident-2025-01-bots", age_days=30)]}
    }
    routed_slack_client.client.history_by_channel["C0BOTS"] = history(BOT_MESSAGE, BOT_MESSAGE)

    run_stale_channel_job()

    assert posted_channels(routed_slack_client) == ["C0BOTS"]


def test_only_the_stale_channels_among_several_are_nudged_once_each(routed_slack_client: RoutedSlackEdges) -> None:
    """With a mix of quiet and busy channels, each quiet one gets exactly one post."""
    routed_slack_client.client.channel_pages = {
        None: {
            "ok": True,
            "channels": [
                channel("C0ONE", "incident-2025-01-one", age_days=20),
                channel("C0BUSY", "incident-2025-01-busy", age_days=20),
                channel("C0TWO", "incident-2025-01-two", age_days=40),
            ],
        }
    }
    routed_slack_client.client.history_by_channel["C0BUSY"] = history(USER_MESSAGE)

    run_stale_channel_job()

    assert posted_channels(routed_slack_client) == ["C0ONE", "C0TWO"]


def test_every_page_of_the_channel_listing_is_read(routed_slack_client: RoutedSlackEdges) -> None:
    """A stale channel on the second page is found by following next_cursor."""
    routed_slack_client.client.channel_pages = {
        None: {
            "ok": True,
            "channels": [channel("C0PAGE1", "incident-2025-01-first", age_days=20)],
            "response_metadata": {"next_cursor": "page-2"},
        },
        "page-2": {"ok": True, "channels": [channel("C0PAGE2", "incident-2025-01-second", age_days=20)]},
    }

    run_stale_channel_job()

    assert posted_channels(routed_slack_client) == ["C0PAGE1", "C0PAGE2"]


def test_each_candidate_channel_is_joined_before_its_history_is_read(routed_slack_client: RoutedSlackEdges) -> None:
    """The bot joins an old incident channel, then reads its history."""
    routed_slack_client.client.channel_pages = {
        None: {"ok": True, "channels": [channel("C0STALE", "incident-2025-01-widgets", age_days=20)]}
    }

    run_stale_channel_job()

    sequence = [
        (name, kwargs["channel"])
        for name, kwargs in routed_slack_client.client.calls
        if name.startswith("conversations_") and "channel" in kwargs
    ]
    assert sequence == [("conversations_join", "C0STALE"), ("conversations_history", "C0STALE")]


def test_failed_channel_listing_posts_nothing_and_does_not_raise(routed_slack_client: RoutedSlackEdges) -> None:
    """An ok=False conversations.list ends the run quietly with no notices."""
    routed_slack_client.client.channel_pages = {None: {"ok": False, "error": "ratelimited"}}

    run_stale_channel_job()

    assert posted_channels(routed_slack_client) == []
    assert routed_slack_client.sentinel_events == []


def test_workspace_without_channels_posts_nothing(routed_slack_client: RoutedSlackEdges) -> None:
    """An empty workspace produces no posts and no events."""
    run_stale_channel_job()

    assert posted_channels(routed_slack_client) == []
    assert routed_slack_client.sentinel_events == []
