"""Slack platform adapter for the incident_draft package.

Registers ``/sre incident draft`` as a child of ``sre.incident``. The adapter
owns the Slack-specific work: locating the incident document via the channel's
"Incident report" bookmark, fetching channel history, and resolving display
names. It delegates the drafting to the platform-agnostic
``packages.incident_draft.service``, which reads each heading's template
instructions, answers them from the transcript, and writes the result into a
draft document. The one write into the incident report itself is its timeline
section, which the service replaces via the document port.

The Slack Web API client is captured lazily from the provider at dispatch
time (it only exists after startup); ``slack_sdk`` is imported for typing
only, keeping the package free of a runtime Slack SDK dependency.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from infrastructure.i18n import t
from integrations.slack.models import (
    Argument,
    ArgumentType,
    CommandPayload,
    CommandResponse,
)
from packages.incident_draft.domain import DraftedDocument, TranscriptMessage
from packages.incident_draft.service import (
    DOCUMENT_UNREADABLE_CODE,
    EMPTY_HISTORY_CODE,
    NO_ANSWERS_CODE,
    TRUNCATED_CODE,
    draft_incident_document,
)
from packages.incident_draft.settings import (
    IncidentDraftSettings,
    get_incident_draft_settings,
)

if TYPE_CHECKING:
    from slack_sdk import WebClient

    from integrations.slack.provider import SlackPlatformProvider

logger = structlog.get_logger()

_DOMAIN = "incident_draft"
_INCIDENT_REPORT_BOOKMARK = "Incident report"
_DOC_ID_PATTERN = re.compile(r"https://docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")

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


def register_commands(provider: SlackPlatformProvider) -> None:
    """Register the ``/sre incident draft`` subcommand with the provider.

    The command works with no arguments (drafting from the whole incident
    history) as well as with ``--limit``; a ``fallback_handler`` handles the
    no-argument invocation so the provider does not show help instead of
    running.

    Args:
        provider: Slack platform provider instance.
    """

    def _dispatch(payload: CommandPayload, parsed_args: dict[str, Any]) -> CommandResponse:
        return handle_draft_command(payload, parsed_args, provider.client)

    def _dispatch_default(payload: CommandPayload) -> CommandResponse:
        return handle_draft_command(payload, {}, provider.client)

    provider.register_command(
        command="draft",
        handler=_dispatch,
        parent="sre.incident",
        description=("Draft a filled-in copy of the incident document from this channel's history"),
        description_key=f"{_DOMAIN}.description",
        usage_hint="[--limit 500]",
        examples=["", "--limit 200"],
        example_keys=[f"{_DOMAIN}.examples.default", f"{_DOMAIN}.examples.limit"],
        arguments=[
            Argument(
                name="--limit",
                type=ArgumentType.INTEGER,
                required=False,
                description="Maximum number of channel messages to draft from",
            ),
        ],
        fallback_handler=_dispatch_default,
    )


def handle_draft_command(
    payload: CommandPayload,
    parsed_args: dict[str, Any],
    client: WebClient | None,
) -> CommandResponse:
    """Handle ``/sre incident draft`` and report the outcome ephemerally.

    Follows the five-step handler discipline: parse (framework) -> typed
    values -> gather inputs + one service call -> ``OperationResult`` ->
    render. All responses are ephemeral so only the invoking responder sees
    them; the drafted content lands in a new document.

    Args:
        payload: Command payload from the Slack platform provider.
        parsed_args: Parsed ``--limit`` argument (empty for the no-argument
            invocation). History always starts at the channel's creation so the
            draft covers the whole incident.
        client: Slack Web API client, or ``None`` before startup.

    Returns:
        An ephemeral ``CommandResponse`` linking the new draft document, or a
        localized notice/error message.
    """
    locale = payload.user_locale or "en-US"
    log = logger.bind(
        command="incident_draft",
        user_id=payload.user_id,
        channel_id=payload.channel_id,
    )

    if client is None or not payload.channel_id:
        log.warning("incident_draft_no_client_or_channel")
        return _error_response(locale)

    document_id = _find_incident_document_id(client, payload.channel_id, log)
    if not document_id:
        msg = t(
            f"{_DOMAIN}.result.no_document",
            locale,
            "I couldn't find an incident document bookmarked in this channel.",
        )
        return CommandResponse(message=msg, ephemeral=True)

    # Everything past this point is slow -- fetching the channel, one AI call,
    # then several Google Docs round trips. Bolt has already acked, so without
    # this the invoker watches nothing happen for a minute.
    _notify_working(client, payload.channel_id, payload, locale, log)

    settings = get_incident_draft_settings()
    limit = _resolve_limit(parsed_args.get("--limit"), settings)
    oldest = _resolve_channel_start(client, payload.channel_id, settings, log)
    messages = _fetch_transcript(client, payload.channel_id, limit=limit, oldest=oldest, log=log)

    result = asyncio.run(draft_incident_document(document_id, messages))

    if result.is_success:
        return _success_response(result.data, locale)
    return _render_error(result.error_code, locale, log, result)


def _notify_working(
    client: WebClient,
    channel_id: str,
    payload: CommandPayload,
    locale: str,
    log: structlog.stdlib.BoundLogger,
) -> None:
    """Tell the invoker the draft is being written, before the slow work starts.

    Ephemeral, so only they see it. A failure here must never fail the command:
    a missing progress note is a far smaller problem than a lost draft.
    """
    text = t(
        f"{_DOMAIN}.result.working",
        locale,
        "🤖 Reading this channel and drafting the incident report — this usually takes up to a minute. "
        "I'll post a link here when it's ready.",
    )
    try:
        client.chat_postEphemeral(channel=channel_id, user=payload.user_id, text=text)
    except Exception as exc:  # noqa: BLE001 - a missing notice must not fail the draft
        log.warning("incident_draft_progress_notice_failed", error=str(exc))


def _success_response(outcome: DraftedDocument | None, locale: str) -> CommandResponse:
    """Render the one-line confirmation, linking the new draft."""
    if outcome is None:
        return _error_response(locale)

    url = f"https://docs.google.com/document/d/{outcome.document_id}/edit"
    if outcome.partial:
        # Worth saying: later sections are missing because the response ran out,
        # not because the channel had nothing to say about them.
        message = t(
            f"{_DOMAIN}.result.partial",
            locale,
            "Created an AI-generated <{{url}}|draft incident report> from this channel, but the "
            "response ran long and later sections are missing — re-run to fill them in. Copy over "
            "whatever's useful into the original incident doc created when the incident opened.",
            url=url,
        )
        return CommandResponse(message=message.replace("{{url}}", url), ephemeral=True)

    message = t(
        f"{_DOMAIN}.result.header",
        locale,
        "Created an AI-generated <{{url}}|draft incident report> from this channel. "
        "Copy over whatever's useful — all or part — into the original incident doc "
        "created when the incident opened.",
        url=url,
    )
    # t() returns the fallback template verbatim when the catalogue isn't
    # loaded; interpolating here covers both paths (no-op when translated).
    return CommandResponse(message=message.replace("{{url}}", url), ephemeral=True)


def _render_error(
    error_code: str | None,
    locale: str,
    log: structlog.stdlib.BoundLogger,
    result: Any,
) -> CommandResponse:
    """Map service error codes onto localized ephemeral notices."""
    if error_code == DOCUMENT_UNREADABLE_CODE:
        msg = t(
            f"{_DOMAIN}.result.unreadable",
            locale,
            "I couldn't read any sections from the incident document.",
        )
        return CommandResponse(message=msg, ephemeral=True)
    if error_code == EMPTY_HISTORY_CODE:
        msg = t(
            f"{_DOMAIN}.result.empty_history",
            locale,
            "There's no channel history to draft from yet.",
        )
        return CommandResponse(message=msg, ephemeral=True)
    if error_code == TRUNCATED_CODE:
        msg = t(
            f"{_DOMAIN}.result.truncated",
            locale,
            "⚠️ The AI response was cut off before it finished, so nothing was written — "
            "your existing draft and the report's timeline are unchanged. Try again, or "
            "raise INCIDENT_DRAFT__MAX_OUTPUT_TOKENS if it keeps happening.",
        )
        return CommandResponse(message=msg, ephemeral=True)
    if error_code == NO_ANSWERS_CODE:
        msg = t(
            f"{_DOMAIN}.result.no_answers",
            locale,
            "The channel history didn't answer any of the document's sections, so no draft was created.",
        )
        return CommandResponse(message=msg, ephemeral=True)

    log.warning(
        "incident_draft_service_error",
        status=getattr(result, "status", None),
        error_code=error_code,
        error=getattr(result, "message", None),
    )
    return _error_response(locale)


def _find_incident_document_id(
    client: WebClient,
    channel_id: str,
    log: structlog.stdlib.BoundLogger,
) -> str | None:
    """Extract the incident document id from the channel's bookmarks.

    Incident channels carry an "Incident report" bookmark pointing at the
    generated Google Doc. Returns ``None`` when the bookmark or its document id
    cannot be found (including on any Slack API failure).
    """
    try:
        response = client.bookmarks_list(channel_id=channel_id)
    except Exception as exc:  # noqa: BLE001 - degrade to "no document" on any API error
        log.warning("incident_draft_bookmarks_fetch_failed", error=str(exc))
        return None

    for bookmark in response.get("bookmarks") or []:
        if bookmark.get("title") != _INCIDENT_REPORT_BOOKMARK:
            continue
        match = _DOC_ID_PATTERN.search(bookmark.get("link") or "")
        if match:
            return match.group(1)
        log.warning("incident_draft_bookmark_link_invalid", link=bookmark.get("link"))
    return None


def _fetch_transcript(
    client: WebClient,
    channel_id: str,
    *,
    limit: int,
    oldest: float,
    log: structlog.stdlib.BoundLogger,
) -> list[TranscriptMessage]:
    """Fetch channel history and resolve authors into transcript messages.

    Returns messages in chronological order. On any Slack API failure an empty
    list is returned so the caller renders the empty-history path.
    """
    try:
        response = client.conversations_history(channel=channel_id, limit=limit, oldest=f"{oldest:.6f}")
    except Exception as exc:  # noqa: BLE001 - degrade to empty history on any API error
        log.warning("incident_draft_history_fetch_failed", error=str(exc))
        return []

    raw_messages = response.get("messages") or []
    name_cache: dict[str, str] = {}
    messages: list[TranscriptMessage] = []
    identity = _resolve_self_identity(client, log)
    skipped_own = 0

    # conversations_history returns newest-first; draft chronologically.
    for raw in reversed(raw_messages):
        text = (raw.get("text") or "").strip()
        user_id = raw.get("user")
        if not text or not user_id:
            continue
        if _is_channel_event(raw):
            # "set the channel topic", joins/leaves and similar system events
            # are channel plumbing, never incident facts.
            skipped_own += 1
            continue
        author = _resolve_display_name(client, user_id, name_cache, log)
        if _is_own_message(raw, author, identity):
            # This bot's own posts (topic changes, hangout links, "an incident
            # report has been created at...") are scaffolding. Other bots are
            # kept: an alerting bot's message is often the first real event.
            skipped_own += 1
            continue
        messages.append(TranscriptMessage(author=author, text=text, timestamp=_format_time(raw.get("ts"))))

    log.info(
        "incident_draft_history_fetched",
        raw_count=len(raw_messages),
        kept_count=len(messages),
        skipped_own_messages=skipped_own,
    )
    return messages


def _resolve_self_identity(client: WebClient, log: structlog.stdlib.BoundLogger) -> dict[str, str]:
    """Return this bot's own ``user_id``, ``bot_id`` and name from ``auth_test``.

    Matching on the user id alone proved unreliable -- depending on how a
    message was posted it may carry only a ``bot_id``, or a display name that
    differs from the authenticated user. All three signals are collected so
    ``_is_own_message`` can match on any of them. Returns an empty mapping if
    the lookup fails, which disables the filter rather than failing the draft.
    """
    try:
        response = client.auth_test()
    except Exception as exc:  # noqa: BLE001 - a failed lookup must not fail the draft
        log.warning("incident_draft_auth_test_failed", error=str(exc))
        return {}

    identity = {
        "user_id": str(response.get("user_id") or ""),
        "bot_id": str(response.get("bot_id") or ""),
        "name": _normalize_name(str(response.get("user") or "")),
    }
    log.info("incident_draft_self_identity", **identity)
    return identity


def _is_own_message(raw: dict[str, Any], author: str, identity: dict[str, str]) -> bool:
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


def _is_channel_event(raw: dict[str, Any]) -> bool:
    """Whether a message is a Slack system event rather than someone talking."""
    subtype = str(raw.get("subtype") or "")
    return subtype.startswith("channel_") or subtype in _SYSTEM_SUBTYPES


def _normalize_name(name: str) -> str:
    """Reduce a Slack name to a comparable form (``SRE Dev`` -> ``sredev``)."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _format_time(raw_ts: Any) -> str:
    """Format a Slack ``ts`` as ``YYYY-MM-DD HH:MM`` UTC.

    The date matters: incidents span days, and the report's impact/detection
    fields want a full timestamp even though timeline entries show only the
    clock time. Returns an empty string for a missing or malformed value; the
    transcript line then simply carries no time.
    """
    try:
        return datetime.fromtimestamp(float(raw_ts), tz=UTC).strftime("%Y-%m-%d %H:%M")
    except TypeError, ValueError:
        return ""


def _resolve_display_name(
    client: WebClient,
    user_id: str,
    cache: dict[str, str],
    log: structlog.stdlib.BoundLogger,
) -> str:
    """Resolve a Slack user's display name, caching lookups; fall back to the id."""
    if user_id in cache:
        return cache[user_id]

    name = user_id
    try:
        info = client.users_info(user=user_id)
        user: dict[str, Any] = info.get("user") or {}
        profile: dict[str, Any] = user.get("profile") or {}
        name = profile.get("display_name") or profile.get("real_name") or user.get("real_name") or user_id
    except Exception as exc:  # noqa: BLE001 - a missing name must not fail the draft
        log.warning("incident_draft_user_lookup_failed", user_id=user_id, error=str(exc))

    cache[user_id] = name
    return name


def _resolve_limit(raw: Any, settings: IncidentDraftSettings) -> int:
    """Coerce the ``--limit`` value into a safe, capped message count."""
    if raw is None:
        return settings.DEFAULT_HISTORY_LIMIT
    try:
        limit = int(raw)
    except TypeError, ValueError:
        return settings.DEFAULT_HISTORY_LIMIT
    if limit <= 0:
        return settings.DEFAULT_HISTORY_LIMIT
    return min(limit, settings.MAX_HISTORY_LIMIT)


def _resolve_channel_start(
    client: WebClient,
    channel_id: str,
    settings: IncidentDraftSettings,
    log: structlog.stdlib.BoundLogger,
) -> float:
    """Return the channel's creation time as a Unix ``oldest`` timestamp.

    Falls back to the configured default window if the channel info lookup
    fails, so a missing ``channels:read``/``groups:read`` scope degrades
    gracefully instead of failing the draft.
    """
    try:
        info = client.conversations_info(channel=channel_id)
        created = (info.get("channel") or {}).get("created")
        if created is not None:
            return float(created)
    except Exception as exc:  # noqa: BLE001 - degrade to default window on any API error
        log.warning("incident_draft_channel_info_failed", error=str(exc))

    return time.time() - settings.DEFAULT_SINCE_HOURS * 3600


def _error_response(locale: str) -> CommandResponse:
    """Build the generic ephemeral error response."""
    msg = t(
        f"{_DOMAIN}.result.error",
        locale,
        "❌ Couldn't create the draft document right now. Please try again shortly.",
    )
    return CommandResponse(message=msg, ephemeral=True)
