"""Unit tests for reading an incident conversation's transcript from Slack."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from packages.incident.core.adapters.slack import SlackIncidentTranscriptReader
from packages.incident.core.domain import TranscriptMessage

pytestmark = pytest.mark.unit

_SINCE = datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)  # 1_700_000_000
_SYSTEM_SUBTYPES = (
    "bot_add",
    "bot_remove",
    "pinned_item",
    "unpinned_item",
    "group_join",
    "group_leave",
    "group_topic",
    "group_purpose",
    "group_name",
    "reminder_add",
    "tombstone",
)


def _client(
    messages: list[dict[str, Any]],
    *,
    users: dict[str, dict[str, Any]] | None = None,
    identity: dict[str, Any] | None = None,
) -> MagicMock:
    """Return a fake Web client serving ``messages`` newest first, ``users`` by id and ``identity`` from auth.test."""
    client = MagicMock(spec=WebClient)
    client.conversations_history.return_value = {"ok": True, "messages": messages}
    known = users or {}
    client.users_info.side_effect = lambda user: {"ok": True, "user": known.get(user, {})}
    client.auth_test.return_value = {"ok": True, **(identity or {})}
    return client


def _read(client: MagicMock, *, exclude: bool = False, limit: int = 50) -> list[TranscriptMessage]:
    reader = SlackIncidentTranscriptReader(client)
    return list(reader.read_transcript("C123", since=_SINCE, limit=limit, exclude_own_and_system_messages=exclude))


def _slack_error() -> SlackApiError:
    return SlackApiError("boom", {"ok": False, "error": "ratelimited"})


class TestReadTranscript:
    def test_newest_first_history_comes_back_chronological_with_names_and_times(self) -> None:
        """Slack lists newest first; the transcript is oldest first, with display names and UTC times."""
        client = _client(
            [
                {"user": "U2", "text": "rolled back", "ts": "1700000120.000200"},
                {"user": "U1", "text": "  seeing 500s  ", "ts": "1700000060.000100"},
            ],
            users={
                "U1": {"profile": {"display_name": "Alice"}},
                "U2": {"profile": {"display_name": "Bob"}},
            },
        )

        messages = _read(client)

        assert messages == [
            TranscriptMessage(
                author="Alice",
                text="seeing 500s",
                posted_at=datetime.fromtimestamp(1700000060.0001, tz=UTC),
            ),
            TranscriptMessage(
                author="Bob",
                text="rolled back",
                posted_at=datetime.fromtimestamp(1700000120.0002, tz=UTC),
            ),
        ]
        assert all(m.posted_at is not None and m.posted_at.tzinfo is UTC for m in messages)

    @pytest.mark.parametrize(
        ("since", "oldest"),
        [
            (datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC), "1700000000.000000"),
            (datetime(2023, 11, 14, 22, 13, 20, 250000, tzinfo=UTC), "1700000000.250000"),
        ],
    )
    def test_since_is_sent_as_oldest_with_six_decimals_and_limit_is_passed_through(self, since: datetime, oldest: str) -> None:
        """The window start reaches Slack as a six-decimal epoch string, for whole and fractional seconds."""
        client = _client([])

        SlackIncidentTranscriptReader(client).read_transcript("C123", since=since, limit=25)

        client.conversations_history.assert_called_once_with(channel="C123", limit=25, oldest=oldest)

    def test_messages_without_text_or_without_a_user_are_dropped(self) -> None:
        """Blank text and user-less entries carry nothing to attribute, so they never reach the transcript."""
        client = _client(
            [
                {"user": "U1", "text": "kept", "ts": "4"},
                {"text": "no user", "ts": "3"},
                {"user": "U1", "text": "   ", "ts": "2"},
                {"user": "U1", "ts": "1"},
            ]
        )

        assert [m.text for m in _read(client)] == ["kept"]

    @pytest.mark.parametrize(
        ("user", "expected"),
        [
            ({"profile": {"display_name": "Disp", "real_name": "Prof Real"}, "real_name": "User Real"}, "Disp"),
            ({"profile": {"display_name": "", "real_name": "Prof Real"}, "real_name": "User Real"}, "Prof Real"),
            ({"profile": {}, "real_name": "User Real"}, "User Real"),
            ({"real_name": "User Real"}, "User Real"),
            ({}, "U1"),
        ],
    )
    def test_author_falls_back_from_display_name_to_real_names_to_the_user_id(self, user: dict[str, Any], expected: str) -> None:
        """The author is the first non-empty of display name, profile real name, user real name, user id."""
        client = _client([{"user": "U1", "text": "hi", "ts": "1"}], users={"U1": user})

        assert [m.author for m in _read(client)] == [expected]

    def test_each_distinct_user_is_looked_up_once_per_read(self) -> None:
        """Names are cached within a read, so a chatty author costs one lookup."""
        client = _client(
            [
                {"user": "U1", "text": "three", "ts": "3"},
                {"user": "U2", "text": "two", "ts": "2"},
                {"user": "U1", "text": "one", "ts": "1"},
            ]
        )

        _read(client)

        assert sorted(call.kwargs["user"] for call in client.users_info.call_args_list) == ["U1", "U2"]

    @pytest.mark.parametrize("ts", [None, "not-a-time", ""])
    def test_missing_or_malformed_time_gives_a_message_without_posted_at(self, ts: str | None) -> None:
        """A message whose time cannot be read is kept, with no time."""
        raw: dict[str, Any] = {"user": "U1", "text": "hi"}
        if ts is not None:
            raw["ts"] = ts
        client = _client([raw])

        messages = _read(client)

        assert [(m.text, m.posted_at) for m in messages] == [("hi", None)]

    def test_unfiltered_read_keeps_own_and_system_messages_and_never_asks_who_the_bot_is(self) -> None:
        """Without the filter, the bot's own posts and system events are transcript lines and auth.test is not called."""
        client = _client(
            [
                {"user": "U1", "text": "joined", "subtype": "channel_join", "ts": "3"},
                {"user": "UBOT", "bot_id": "B1", "text": "incident created", "ts": "2"},
                {"user": "U1", "text": "hello", "ts": "1"},
            ],
            identity={"user_id": "UBOT", "bot_id": "B1", "user": "sre-bot"},
        )

        assert [m.text for m in _read(client)] == ["hello", "incident created", "joined"]
        client.auth_test.assert_not_called()


class TestReadTranscriptFiltered:
    def test_own_message_is_dropped_when_matched_by_user_id(self) -> None:
        """A message posted under the bot's user id is scaffolding, not conversation."""
        client = _client(
            [{"user": "UBOT", "text": "report created", "ts": "2"}, {"user": "U1", "text": "hello", "ts": "1"}],
            identity={"user_id": "UBOT", "bot_id": "B1", "user": "sre-bot"},
        )

        assert [m.text for m in _read(client, exclude=True)] == ["hello"]

    def test_own_message_is_dropped_when_matched_by_bot_id_alone(self) -> None:
        """A post carrying the bot's bot id under another user id is still the bot's."""
        client = _client(
            [{"user": "UOTHER", "bot_id": "B1", "text": "report created", "ts": "2"}, {"user": "U1", "text": "hello", "ts": "1"}],
            identity={"user_id": "UBOT", "bot_id": "B1", "user": "sre-bot"},
        )

        assert [m.text for m in _read(client, exclude=True)] == ["hello"]

    def test_own_message_is_dropped_when_matched_by_normalized_name_alone(self) -> None:
        """A post whose resolved author name normalizes to the bot's name is the bot's, whatever its ids."""
        client = _client(
            [{"user": "UOTHER", "text": "report created", "ts": "2"}, {"user": "U1", "text": "hello", "ts": "1"}],
            users={"UOTHER": {"profile": {"display_name": "SRE Bot"}}, "U1": {"profile": {"display_name": "Alice"}}},
            identity={"user_id": "UBOT", "bot_id": "B1", "user": "sre-bot"},
        )

        assert [m.text for m in _read(client, exclude=True)] == ["hello"]

    def test_another_bot_is_kept(self) -> None:
        """An alerting bot's message is often the first real event, so only this bot is filtered."""
        client = _client(
            [{"user": "UALERT", "bot_id": "B9", "text": "ALARM: 5xx", "ts": "1"}],
            users={"UALERT": {"profile": {"display_name": "Alertmanager"}}},
            identity={"user_id": "UBOT", "bot_id": "B1", "user": "sre-bot"},
        )

        assert [m.author for m in _read(client, exclude=True)] == ["Alertmanager"]

    def test_a_similarly_named_human_is_kept(self) -> None:
        """Name matching is exact after normalization, so a person named like the bot plus more is not filtered."""
        client = _client(
            [{"user": "U7", "text": "I'm on it", "ts": "1"}],
            users={"U7": {"profile": {"display_name": "SRE Bot Fan"}}},
            identity={"user_id": "UBOT", "bot_id": "B1", "user": "sre-bot"},
        )

        assert [m.text for m in _read(client, exclude=True)] == ["I'm on it"]

    @pytest.mark.parametrize("subtype", [*_SYSTEM_SUBTYPES, "channel_join", "channel_topic", "channel_anything"])
    def test_system_events_are_dropped_before_the_author_is_resolved(self, subtype: str) -> None:
        """Joins, topic changes and similar plumbing are dropped without spending a user lookup on them."""
        client = _client(
            [{"user": "U1", "text": "system text", "subtype": subtype, "ts": "1"}],
            identity={"user_id": "UBOT", "bot_id": "B1", "user": "sre-bot"},
        )

        assert _read(client, exclude=True) == []
        client.users_info.assert_not_called()

    def test_bot_identity_is_asked_once_per_read_after_the_history_call(self) -> None:
        """One auth.test per filtered read, issued after the history fetch."""
        client = _client(
            [{"user": "U1", "text": "two", "ts": "2"}, {"user": "U1", "text": "one", "ts": "1"}],
            identity={"user_id": "UBOT", "bot_id": "B1", "user": "sre-bot"},
        )

        _read(client, exclude=True)

        client.auth_test.assert_called_once_with()
        names = [call[0] for call in client.method_calls]
        assert names.index("conversations_history") < names.index("auth_test")


class TestReadTranscriptFailures:
    def test_history_failure_gives_an_empty_transcript(self) -> None:
        """A failed history call degrades to no messages; the caller renders its empty-history path."""
        client = _client([])
        client.conversations_history.side_effect = _slack_error()

        assert _read(client) == []
        assert _read(client, exclude=True) == []

    def test_user_lookup_failure_uses_the_user_id_as_author(self) -> None:
        """A name that cannot be resolved never drops the message."""
        client = _client([{"user": "U1", "text": "hi", "ts": "1"}])
        client.users_info.side_effect = _slack_error()

        assert [(m.author, m.text) for m in _read(client)] == [("U1", "hi")]

    def test_identity_failure_filters_nothing_as_own(self) -> None:
        """When the bot cannot learn who it is, every non-system message is kept; system events are still dropped."""
        client = _client(
            [
                {"user": "U1", "text": "joined", "subtype": "channel_join", "ts": "3"},
                {"user": "UBOT", "bot_id": "B1", "text": "report created", "ts": "2"},
                {"user": "U1", "text": "hello", "ts": "1"},
            ]
        )
        client.auth_test.side_effect = _slack_error()

        assert [m.text for m in _read(client, exclude=True)] == ["hello", "report created"]
