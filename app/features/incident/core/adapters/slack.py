"""Slack adapter implementing ``IncidentTranscriptReader`` on the Slack Web API.

The adapter owns everything Slack-shaped about a transcript: the history and
thread-replies calls, their cursor paging and timestamp format, display-name
resolution, chronological ordering, and
the optional filtering of this bot's own posts and Slack system events. It also
owns every degradation: a Web API failure is logged here and never raised.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import structlog
from slack_sdk import WebClient
from slack_sdk.web import SlackResponse

from features.incident.core.domain import TranscriptMessage
from integrations.slack.client import get_slack_web_client

logger = structlog.get_logger()

# Slack system events that are channel plumbing, not incident conversation.
_SYSTEM_SUBTYPES = frozenset(
    {
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
    }
)


class SlackIncidentTranscriptReader:
    """Read an incident conversation's start time and transcript from Slack."""

    def __init__(self, client: WebClient) -> None:
        self._client = client

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        """Return the channel's creation time, or ``None`` when Slack cannot say.

        A failed ``conversations.info`` call (a missing ``channels:read`` or
        ``groups:read`` scope, for one) degrades to ``None``.
        """
        log = logger.bind(conversation_id=conversation_id)
        try:
            response = self._client.conversations_info(channel=conversation_id)
            created = (response.get("channel") or {}).get("created")
            if created is None:
                return None
            return datetime.fromtimestamp(float(created), tz=UTC)
        except Exception as exc:  # noqa: BLE001 - degrade to "unknown" on any API error
            log.warning("incident_transcript_conversation_info_failed", error=str(exc))
            return None

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        """Return the channel's messages since ``since``, thread replies included, oldest first.

        Decisive facts often land in threads, so every message Slack reports
        replies for is expanded with them. ``limit`` caps the whole transcript
        and the newest messages are kept. A failed first history page returns
        an empty sequence, so the caller renders its empty-history path; a
        failed later page or thread is logged and skipped.
        """
        log = logger.bind(conversation_id=conversation_id)
        try:
            top_level = self._read_history(conversation_id, since=since, limit=limit, log=log)
        except Exception as exc:  # noqa: BLE001 - degrade to empty history on any API error
            log.warning("incident_transcript_history_fetch_failed", error=str(exc))
            return []

        raw_messages = _merge_chronologically(top_level, self._read_thread_replies(conversation_id, top_level, limit, log))[
            -limit:
        ]

        name_cache: dict[str, str] = {}
        messages: list[TranscriptMessage] = []
        identity = self._resolve_self_identity(log) if exclude_own_and_system_messages else {}
        skipped = 0

        for raw in raw_messages:
            text = (raw.get("text") or "").strip()
            user_id = raw.get("user")
            if not text or not (user_id or raw.get("bot_id")):
                continue
            if exclude_own_and_system_messages and _is_channel_event(raw):
                # "set the channel topic", joins/leaves and similar system events
                # are channel plumbing, never incident facts.
                skipped += 1
                continue
            # Webhook and alerting posts carry only a bot id; they are named
            # from their bot fields rather than looked up as a user.
            author = self._resolve_display_name(user_id, name_cache, log) if user_id else _bot_name(raw)
            if _is_own_message(raw, author, identity):
                # This bot's own posts (topic changes, hangout links, "an incident
                # report has been created at...") are scaffolding. Other bots are
                # kept: an alerting bot's message is often the first real event.
                skipped += 1
                continue
            messages.append(
                TranscriptMessage(author=author, text=text, posted_at=_posted_at(raw.get("ts")), is_bot=_is_bot_post(raw))
            )

        log.info(
            "incident_transcript_history_fetched",
            raw_count=len(raw_messages),
            kept_count=len(messages),
            skipped_own_and_system_messages=skipped,
        )
        return messages

    def _read_history(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        log: structlog.stdlib.BoundLogger,
    ) -> list[Mapping[str, Any]]:
        """Return up to ``limit`` top-level messages since ``since``, oldest first.

        Follows Slack's cursor across pages. The first page's failure is raised
        for the caller to degrade; a later page's failure keeps what was read.
        """
        newest_first: list[Mapping[str, Any]] = []
        cursor = ""
        while len(newest_first) < limit:
            kwargs: dict[str, Any] = {
                "channel": conversation_id,
                "limit": limit - len(newest_first),
                "oldest": f"{since.timestamp():.6f}",
            }
            if cursor:
                kwargs["cursor"] = cursor
            try:
                response = self._client.conversations_history(**kwargs)
            except Exception as exc:
                if not cursor:
                    raise
                log.warning("incident_transcript_history_page_failed", error=str(exc), read_so_far=len(newest_first))
                break
            newest_first.extend(response.get("messages") or [])
            cursor = _next_cursor(response)
            if not cursor:
                break
        # conversations_history returns newest-first; the transcript is chronological.
        return list(reversed(newest_first[:limit]))

    def _read_thread_replies(
        self,
        conversation_id: str,
        top_level: Sequence[Mapping[str, Any]],
        limit: int,
        log: structlog.stdlib.BoundLogger,
    ) -> list[Mapping[str, Any]]:
        """Return the replies of every threaded top-level message, without the parents.

        A thread whose replies cannot be read is logged and skipped.
        """
        replies: list[Mapping[str, Any]] = []
        for parent in top_level:
            thread_ts = parent.get("ts")
            if not thread_ts or not parent.get("reply_count"):
                continue
            cursor = ""
            try:
                while True:
                    kwargs: dict[str, Any] = {"channel": conversation_id, "ts": thread_ts, "limit": limit}
                    if cursor:
                        kwargs["cursor"] = cursor
                    response = self._client.conversations_replies(**kwargs)
                    # Slack repeats the parent as the first message of every thread read.
                    replies.extend(m for m in response.get("messages") or [] if m.get("ts") != thread_ts)
                    cursor = _next_cursor(response)
                    if not cursor:
                        break
            except Exception as exc:  # noqa: BLE001 - one unreadable thread must not fail the read
                log.warning("incident_transcript_replies_fetch_failed", thread_ts=thread_ts, error=str(exc))
        return replies

    def _resolve_self_identity(self, log: structlog.stdlib.BoundLogger) -> dict[str, str]:
        """Return this bot's own ``user_id``, ``bot_id`` and name from ``auth.test``.

        Matching on the user id alone proved unreliable -- depending on how a
        message was posted it may carry only a ``bot_id``, or a display name that
        differs from the authenticated user. All three signals are collected so
        ``_is_own_message`` can match on any of them. Returns an empty mapping if
        the lookup fails, which disables the filter rather than failing the read.
        """
        try:
            response = self._client.auth_test()
        except Exception as exc:  # noqa: BLE001 - a failed lookup must not fail the read
            log.warning("incident_transcript_auth_test_failed", error=str(exc))
            return {}

        identity = {
            "user_id": str(response.get("user_id") or ""),
            "bot_id": str(response.get("bot_id") or ""),
            "name": _normalize_name(str(response.get("user") or "")),
        }
        log.info("incident_transcript_self_identity", **identity)
        return identity

    def _resolve_display_name(
        self,
        user_id: str,
        cache: dict[str, str],
        log: structlog.stdlib.BoundLogger,
    ) -> str:
        """Resolve a Slack user's display name, caching lookups; fall back to the id."""
        if user_id in cache:
            return cache[user_id]

        name = user_id
        try:
            user: Mapping[str, Any] = self._client.users_info(user=user_id).get("user") or {}
            profile: Mapping[str, Any] = user.get("profile") or {}
            name = profile.get("display_name") or profile.get("real_name") or user.get("real_name") or user_id
        except Exception as exc:  # noqa: BLE001 - a missing name must not drop the message
            log.warning("incident_transcript_user_lookup_failed", user_id=user_id, error=str(exc))

        cache[user_id] = name
        return name


def build_incident_transcript_reader() -> SlackIncidentTranscriptReader:
    """Build the adapter on the bot's Web client."""
    return SlackIncidentTranscriptReader(get_slack_web_client())


def _is_own_message(raw: Mapping[str, Any], author: str, identity: dict[str, str]) -> bool:
    """Whether a message was posted by this bot, matched on any known signal."""
    if not identity:
        return False
    if identity.get("user_id") and raw.get("user") == identity["user_id"]:
        return True
    if identity.get("bot_id") and raw.get("bot_id") == identity["bot_id"]:
        return True
    # Display name is the last resort: it catches posts made under an identity
    # auth_test does not report, which is how bot messages slipped through.
    own_name = identity.get("name")
    return bool(own_name) and _normalize_name(author) == own_name


def _is_channel_event(raw: Mapping[str, Any]) -> bool:
    """Whether a message is a Slack system event rather than someone talking."""
    subtype = str(raw.get("subtype") or "")
    return subtype.startswith("channel_") or subtype in _SYSTEM_SUBTYPES


def _is_bot_post(raw: Mapping[str, Any]) -> bool:
    """Whether a bot or an integration posted the message rather than a person."""
    return bool(raw.get("bot_id")) or raw.get("subtype") == "bot_message"


def _bot_name(raw: Mapping[str, Any]) -> str:
    """Name a user-less bot post by its username, then its bot profile name, then its bot id."""
    profile: Mapping[str, Any] = raw.get("bot_profile") or {}
    return str(raw.get("username") or profile.get("name") or raw.get("bot_id"))


def _normalize_name(name: str) -> str:
    """Reduce a Slack name to a comparable form (``SRE Dev`` -> ``sredev``)."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _next_cursor(response: SlackResponse | Mapping[str, Any]) -> str:
    """Return the cursor of the next page, or ``""`` when this was the last one."""
    return str((response.get("response_metadata") or {}).get("next_cursor") or "")


def _merge_chronologically(
    top_level: Sequence[Mapping[str, Any]], replies: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """Interleave replies with the top-level messages by time, each ``ts`` once.

    A reply broadcast to the channel is in both lists and is kept once. A
    top-level message with an unreadable time stays right after the message
    before it, so it never jumps to the start or end of the transcript.
    """
    seen = {str(raw.get("ts")) for raw in top_level if raw.get("ts")}
    keyed: list[tuple[float, int, Mapping[str, Any]]] = []
    previous = float("-inf")
    for position, raw in enumerate(top_level):
        posted_at = _posted_at(raw.get("ts"))
        previous = posted_at.timestamp() if posted_at else previous
        keyed.append((previous, position, raw))
    for position, raw in enumerate(replies, start=len(top_level)):
        posted_at = _posted_at(raw.get("ts"))
        if posted_at is None or str(raw.get("ts")) in seen:
            continue
        seen.add(str(raw.get("ts")))
        keyed.append((posted_at.timestamp(), position, raw))
    return [raw for _, _, raw in sorted(keyed, key=lambda item: (item[0], item[1]))]


def _posted_at(raw_ts: Any) -> datetime | None:
    """Convert a Slack ``ts`` to an aware UTC datetime; ``None`` when missing or malformed."""
    try:
        return datetime.fromtimestamp(float(raw_ts), tz=UTC)
    except TypeError, ValueError:
        return None
