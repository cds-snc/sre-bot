"""Slack adapter implementing ``IncidentTranscriptReader`` on the Slack Web API.

The adapter owns everything Slack-shaped about a transcript: the history call
and its timestamp format, display-name resolution, chronological ordering, and
the optional filtering of this bot's own posts and Slack system events. It also
owns every degradation: a Web API failure is logged here and never raised.
"""

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import structlog
from slack_sdk import WebClient

from integrations.slack.client import get_slack_web_client
from packages.incident.core.domain import TranscriptMessage

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
        """Return the channel's messages since ``since``, oldest first.

        On any Slack API failure of the history call an empty sequence is
        returned, so the caller renders its empty-history path.
        """
        log = logger.bind(conversation_id=conversation_id)
        try:
            response = self._client.conversations_history(
                channel=conversation_id,
                limit=limit,
                oldest=f"{since.timestamp():.6f}",
            )
            raw_messages: Sequence[Mapping[str, Any]] = response.get("messages") or []
        except Exception as exc:  # noqa: BLE001 - degrade to empty history on any API error
            log.warning("incident_transcript_history_fetch_failed", error=str(exc))
            return []

        name_cache: dict[str, str] = {}
        messages: list[TranscriptMessage] = []
        identity = self._resolve_self_identity(log) if exclude_own_and_system_messages else {}
        skipped = 0

        # conversations_history returns newest-first; the transcript is chronological.
        for raw in reversed(raw_messages):
            text = (raw.get("text") or "").strip()
            user_id = raw.get("user")
            if not text or not user_id:
                continue
            if exclude_own_and_system_messages and _is_channel_event(raw):
                # "set the channel topic", joins/leaves and similar system events
                # are channel plumbing, never incident facts.
                skipped += 1
                continue
            author = self._resolve_display_name(user_id, name_cache, log)
            if _is_own_message(raw, author, identity):
                # This bot's own posts (topic changes, hangout links, "an incident
                # report has been created at...") are scaffolding. Other bots are
                # kept: an alerting bot's message is often the first real event.
                skipped += 1
                continue
            messages.append(TranscriptMessage(author=author, text=text, posted_at=_posted_at(raw.get("ts"))))

        log.info(
            "incident_transcript_history_fetched",
            raw_count=len(raw_messages),
            kept_count=len(messages),
            skipped_own_and_system_messages=skipped,
        )
        return messages

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


def _normalize_name(name: str) -> str:
    """Reduce a Slack name to a comparable form (``SRE Dev`` -> ``sredev``)."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _posted_at(raw_ts: Any) -> datetime | None:
    """Convert a Slack ``ts`` to an aware UTC datetime; ``None`` when missing or malformed."""
    try:
        return datetime.fromtimestamp(float(raw_ts), tz=UTC)
    except TypeError, ValueError:
        return None
