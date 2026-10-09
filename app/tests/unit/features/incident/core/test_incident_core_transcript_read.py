"""Unit tests for reading an incident conversation's transcript from Slack."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from structlog.testing import capture_logs

from features.incident.core.adapters.slack import SlackIncidentTranscriptReader
from features.incident.core.domain import TranscriptMessage

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

    def test_messages_without_text_or_without_any_poster_are_dropped(self) -> None:
        """Blank text, and entries with neither a user nor a bot id, carry nothing to attribute."""
        client = _client(
            [
                {"user": "U1", "text": "kept", "ts": "4"},
                {"text": "no poster", "ts": "3"},
                {"user": "U1", "text": "   ", "ts": "2"},
                {"user": "U1", "ts": "1"},
            ]
        )

        assert [m.text for m in _read(client)] == ["kept"]

    @pytest.mark.parametrize(
        ("raw", "expected_author"),
        [
            ({"bot_id": "B9", "username": "Alertmanager", "bot_profile": {"name": "alerts"}}, "Alertmanager"),
            ({"bot_id": "B9", "bot_profile": {"name": "alerts"}}, "alerts"),
            ({"bot_id": "B9"}, "B9"),
        ],
    )
    def test_a_bot_post_without_a_user_is_kept_and_named_from_its_bot_fields(
        self, raw: dict[str, Any], expected_author: str
    ) -> None:
        """Webhook and alerting posts carry only a bot id; they are incident facts, named by username, bot profile, then bot id."""
        client = _client([{**raw, "text": "ALARM: 5xx", "ts": "1"}])

        messages = _read(client)

        assert [(m.author, m.text, m.is_bot) for m in messages] == [(expected_author, "ALARM: 5xx", True)]
        client.users_info.assert_not_called()

    @pytest.mark.parametrize(
        ("raw", "is_bot"),
        [
            ({"user": "U1"}, False),
            ({"user": "UALERT", "bot_id": "B9"}, True),
            ({"user": "UALERT", "subtype": "bot_message"}, True),
        ],
    )
    def test_messages_are_flagged_as_bot_posts_from_their_bot_id_or_subtype(self, raw: dict[str, Any], is_bot: bool) -> None:
        """A consumer can tell people from bots: a bot id or the bot_message subtype marks a bot post."""
        client = _client([{**raw, "text": "hello", "ts": "1"}])

        assert [m.is_bot for m in _read(client)] == [is_bot]

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

    def test_this_bots_post_without_a_user_is_still_dropped_by_bot_id(self) -> None:
        """Keeping user-less bot posts must not let this bot's own scaffolding back in."""
        client = _client(
            [
                {"bot_id": "B1", "username": "sre-bot", "text": "report created", "ts": "2"},
                {"user": "U1", "text": "hello", "ts": "1"},
            ],
            identity={"user_id": "UBOT", "bot_id": "B1", "user": "sre-bot"},
        )

        assert [m.text for m in _read(client, exclude=True)] == ["hello"]

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


def _paged_client(
    history_pages: list[list[dict[str, Any]]],
    replies: dict[str, list[list[dict[str, Any]]]] | None = None,
    *,
    identity: dict[str, Any] | None = None,
) -> MagicMock:
    """Return a fake Web client serving history and per-thread replies as cursor-linked pages.

    Page ``n`` carries ``next_cursor`` ``"<kind>-<n+1>"`` when another page follows.
    Every author is unnamed, so messages are attributed to their user id.
    """
    client = _client([], identity=identity)

    def page(pages: list[list[dict[str, Any]]], kind: str, cursor: str | None) -> dict[str, Any]:
        index = int(cursor.rsplit("-", 1)[1]) if cursor else 0
        more = index + 1 < len(pages)
        return {
            "ok": True,
            "messages": pages[index],
            "has_more": more,
            "response_metadata": {"next_cursor": f"{kind}-{index + 1}" if more else ""},
        }

    def history(**kwargs: Any) -> dict[str, Any]:
        return page(history_pages, "history", kwargs.get("cursor"))

    def thread(**kwargs: Any) -> dict[str, Any]:
        return page((replies or {})[kwargs["ts"]], f"replies:{kwargs['ts']}", kwargs.get("cursor"))

    client.conversations_history.side_effect = history
    client.conversations_replies.side_effect = thread
    return client


def _parent(text: str, ts: str, reply_count: int) -> dict[str, Any]:
    return {"user": "U1", "text": text, "ts": ts, "thread_ts": ts, "reply_count": reply_count}


def _reply(text: str, ts: str, parent_ts: str, **extra: Any) -> dict[str, Any]:
    return {"user": "U2", "text": text, "ts": ts, "thread_ts": parent_ts, **extra}


class TestReadTranscriptThreads:
    def test_thread_replies_are_interleaved_chronologically_without_repeating_the_parent(self) -> None:
        """Replies join the conversation in time order; Slack's leading copy of the parent is not repeated."""
        parent = _parent("prod is down", "1700000100.000000", 2)
        client = _paged_client(
            [[{"user": "U1", "text": "later top-level", "ts": "1700000300.000000"}, parent]],
            {
                "1700000100.000000": [
                    [
                        parent,
                        _reply("deployed the fix", "1700000150.000000", "1700000100.000000"),
                        _reply("confirmed in prod", "1700000400.000000", "1700000100.000000"),
                    ]
                ]
            },
        )

        messages = _read(client)

        assert [m.text for m in messages] == ["prod is down", "deployed the fix", "later top-level", "confirmed in prod"]
        assert messages[1].posted_at == datetime.fromtimestamp(1700000150, tz=UTC)
        client.conversations_replies.assert_called_once_with(channel="C123", ts="1700000100.000000", limit=50)

    def test_messages_without_replies_trigger_no_replies_call(self) -> None:
        """Only messages Slack reports as having replies are expanded."""
        client = _paged_client([[{"user": "U1", "text": "solo", "ts": "1700000100.000000"}]])

        _read(client)

        client.conversations_replies.assert_not_called()

    def test_a_reply_also_sent_to_the_channel_appears_once(self) -> None:
        """A broadcast reply is in both the history and the thread; the transcript holds it once."""
        broadcast = _reply("rolled back", "1700000200.000000", "1700000100.000000", subtype="thread_broadcast")
        parent = _parent("prod is down", "1700000100.000000", 1)
        client = _paged_client([[broadcast, parent]], {"1700000100.000000": [[parent, broadcast]]})

        assert [m.text for m in _read(client)] == ["prod is down", "rolled back"]

    def test_own_posts_and_system_events_in_a_thread_are_filtered_like_top_level_ones(self) -> None:
        """The exclusion rules apply to replies the same way."""
        parent = _parent("prod is down", "1700000100.000000", 3)
        client = _paged_client(
            [[parent]],
            {
                "1700000100.000000": [
                    [
                        parent,
                        {"user": "UBOT", "text": "report created", "ts": "1700000110.000000", "thread_ts": parent["ts"]},
                        _reply("joined", "1700000120.000000", parent["ts"], subtype="channel_join"),
                        _reply("on it", "1700000130.000000", parent["ts"]),
                    ]
                ]
            },
            identity={"user_id": "UBOT", "bot_id": "B1", "user": "sre-bot"},
        )

        assert [m.text for m in _read(client, exclude=True)] == ["prod is down", "on it"]

    def test_a_failed_replies_fetch_skips_only_that_thread_and_is_logged(self) -> None:
        """One unreadable thread never costs the rest of the transcript."""
        parent = _parent("prod is down", "1700000100.000000", 1)
        client = _paged_client([[{"user": "U1", "text": "later", "ts": "1700000300.000000"}, parent]])
        client.conversations_replies.side_effect = _slack_error()

        with capture_logs() as logs:
            messages = _read(client)

        assert [m.text for m in messages] == ["prod is down", "later"]
        assert [log["thread_ts"] for log in logs if log["event"] == "incident_transcript_replies_fetch_failed"] == [
            "1700000100.000000"
        ]


class TestReadTranscriptPagination:
    def test_history_pages_are_followed_until_no_cursor_remains(self) -> None:
        """Every history page is read, each later call carrying the cursor and the remaining budget."""
        client = _paged_client(
            [
                [
                    {"user": "U1", "text": "three", "ts": "1700000300.000000"},
                    {"user": "U1", "text": "two", "ts": "1700000200.000000"},
                ],
                [{"user": "U1", "text": "one", "ts": "1700000100.000000"}],
            ]
        )

        assert [m.text for m in _read(client, limit=50)] == ["one", "two", "three"]
        assert client.conversations_history.call_args_list[1].kwargs == {
            "channel": "C123",
            "limit": 48,
            "oldest": "1700000000.000000",
            "cursor": "history-1",
        }

    def test_history_paging_stops_once_the_limit_is_reached(self) -> None:
        """A full page at the limit ends the read even when Slack offers more."""
        client = _paged_client(
            [
                [
                    {"user": "U1", "text": "three", "ts": "1700000300.000000"},
                    {"user": "U1", "text": "two", "ts": "1700000200.000000"},
                ],
                [{"user": "U1", "text": "one", "ts": "1700000100.000000"}],
            ]
        )

        assert [m.text for m in _read(client, limit=2)] == ["two", "three"]
        assert client.conversations_history.call_count == 1

    def test_a_failed_later_history_page_keeps_the_pages_already_read(self) -> None:
        """Only a failed first page empties the transcript; a later failure is logged and the earlier pages kept."""
        client = _paged_client(
            [
                [{"user": "U1", "text": "two", "ts": "1700000200.000000"}],
                [{"user": "U1", "text": "one", "ts": "1700000100.000000"}],
            ]
        )
        first_page = client.conversations_history.side_effect

        def fail_on_second_page(**kwargs: Any) -> dict[str, Any]:
            if kwargs.get("cursor"):
                raise _slack_error()
            return first_page(**kwargs)

        client.conversations_history.side_effect = fail_on_second_page

        with capture_logs() as logs:
            messages = _read(client)

        assert [m.text for m in messages] == ["two"]
        assert any(log["event"] == "incident_transcript_history_page_failed" for log in logs)

    def test_reply_pages_are_followed_until_no_cursor_remains(self) -> None:
        """A long thread is read across all its pages."""
        parent = _parent("prod is down", "1700000100.000000", 2)
        client = _paged_client(
            [[parent]],
            {
                "1700000100.000000": [
                    [parent, _reply("first", "1700000110.000000", parent["ts"])],
                    [_reply("second", "1700000120.000000", parent["ts"])],
                ]
            },
        )

        assert [m.text for m in _read(client)] == ["prod is down", "first", "second"]
        assert client.conversations_replies.call_args_list[1].kwargs["cursor"] == "replies:1700000100.000000-1"

    def test_the_limit_caps_the_whole_transcript_keeping_the_newest_messages(self) -> None:
        """With replies added, the oldest messages give way so the most recent ``limit`` remain."""
        parent = _parent("prod is down", "1700000100.000000", 1)
        client = _paged_client(
            [[{"user": "U1", "text": "fixed", "ts": "1700000300.000000"}, parent]],
            {"1700000100.000000": [[parent, _reply("rolling back", "1700000200.000000", parent["ts"])]]},
        )

        assert [m.text for m in _read(client, limit=2)] == ["rolling back", "fixed"]
