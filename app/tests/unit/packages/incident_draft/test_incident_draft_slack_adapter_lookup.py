"""Unit tests for the incident_draft Slack channel lookup adapter."""

from unittest.mock import MagicMock

import pytest
from slack_sdk.errors import SlackApiError

from packages.incident_draft.adapters import slack as slack_adapter
from packages.incident_draft.adapters.slack import SlackIncidentChannel, build_incident_channel
from packages.incident_draft.service import IncidentChannelPort

pytestmark = pytest.mark.unit


def test_list_bookmarks_calls_bookmarks_list_and_returns_the_bookmarks() -> None:
    """The channel's bookmarks come back as Slack listed them."""
    bookmarks = [{"title": "Incident report", "link": "https://docs.google.com/document/d/DOC123/edit"}]
    client = MagicMock()
    client.bookmarks_list.return_value = {"ok": True, "bookmarks": bookmarks}

    assert SlackIncidentChannel(client).list_bookmarks("C123") == bookmarks
    client.bookmarks_list.assert_called_once_with(channel_id="C123")


def test_fetch_history_calls_conversations_history_and_returns_messages_newest_first() -> None:
    """History is requested with the caller's window and returned in Slack's order."""
    raw = [{"user": "U1", "text": "newest", "ts": "2"}, {"user": "U1", "text": "oldest", "ts": "1"}]
    client = MagicMock()
    client.conversations_history.return_value = {"ok": True, "messages": raw}

    messages = SlackIncidentChannel(client).fetch_history("C123", limit=25, oldest="1700000000.000000")

    assert messages == raw
    client.conversations_history.assert_called_once_with(channel="C123", limit=25, oldest="1700000000.000000")


def test_get_channel_calls_conversations_info_and_returns_the_channel() -> None:
    """The channel object carries the creation time the handler reads."""
    client = MagicMock()
    client.conversations_info.return_value = {"ok": True, "channel": {"created": 1_700_000_000}}

    assert SlackIncidentChannel(client).get_channel("C123") == {"created": 1_700_000_000}
    client.conversations_info.assert_called_once_with(channel="C123")


def test_get_user_calls_users_info_and_returns_the_user() -> None:
    """The user object carries the profile the handler resolves a display name from."""
    user = {"real_name": "Ada Lovelace", "profile": {"display_name": "Ada"}}
    client = MagicMock()
    client.users_info.return_value = {"ok": True, "user": user}

    assert SlackIncidentChannel(client).get_user("U1") == user
    client.users_info.assert_called_once_with(user="U1")


def test_get_self_identity_calls_auth_test_and_returns_the_bot_identifiers() -> None:
    """The bot's user id, bot id and name are the three signals own-message filtering needs."""
    client = MagicMock()
    client.auth_test.return_value = {"ok": True, "user_id": "UBOT", "bot_id": "BBOT", "user": "sre-bot", "team": "T"}

    identity = SlackIncidentChannel(client).get_self_identity()

    assert identity == {"user_id": "UBOT", "bot_id": "BBOT", "user": "sre-bot"}
    client.auth_test.assert_called_once_with()


def test_missing_payload_keys_yield_empty_values() -> None:
    """A response without the expected key reads as empty rather than raising."""
    client = MagicMock()
    for method in ("bookmarks_list", "conversations_history", "conversations_info", "users_info", "auth_test"):
        getattr(client, method).return_value = {"ok": True}
    channel = SlackIncidentChannel(client)

    assert channel.list_bookmarks("C123") == []
    assert channel.fetch_history("C123", limit=10, oldest="0.000000") == []
    assert channel.get_channel("C123") == {}
    assert channel.get_user("U1") == {}
    assert channel.get_self_identity() == {"user_id": None, "bot_id": None, "user": None}


@pytest.mark.parametrize(
    ("web_api_method", "lookup"),
    [
        ("bookmarks_list", lambda channel: channel.list_bookmarks("C123")),
        ("conversations_history", lambda channel: channel.fetch_history("C123", limit=10, oldest="0.000000")),
        ("conversations_info", lambda channel: channel.get_channel("C123")),
        ("users_info", lambda channel: channel.get_user("U1")),
        ("auth_test", lambda channel: channel.get_self_identity()),
    ],
)
def test_lookups_propagate_slack_api_errors(web_api_method: str, lookup) -> None:
    """The adapter does not swallow Web API errors; the handler owns each degradation."""
    client = MagicMock()
    getattr(client, web_api_method).side_effect = SlackApiError("err", {"ok": False, "error": "missing_scope"})

    with pytest.raises(SlackApiError):
        lookup(SlackIncidentChannel(client))


def test_build_incident_channel_uses_the_bot_web_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """The built adapter satisfies the package Protocol and calls through the shared client factory's client."""
    client = MagicMock()
    client.conversations_info.return_value = {"ok": True, "channel": {"created": 1}}
    monkeypatch.setattr(slack_adapter, "get_slack_web_client", lambda: client)

    channel = build_incident_channel()

    assert isinstance(channel, IncidentChannelPort)
    channel.get_channel("C123")
    client.conversations_info.assert_called_once_with(channel="C123")
