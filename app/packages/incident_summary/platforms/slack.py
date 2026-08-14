"""Slack platform adapter for the incident_summary package.

Registers ``/sre incident summarize`` as a child of ``sre.incident`` and
turns recent channel history into an ephemeral catch-up summary. The adapter
owns the Slack-specific work (fetching history, resolving display names) and
delegates the actual summarization to the platform-agnostic
``packages.incident_summary.service``.

The Slack Web API client is captured lazily from the provider at dispatch
time (it only exists after startup); ``slack_sdk`` is imported for typing
only, keeping the package free of a runtime Slack SDK dependency.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING, Any

import structlog

from infrastructure.i18n import t
from integrations.slack.models import (
    Argument,
    ArgumentType,
    CommandPayload,
    CommandResponse,
)
from packages.incident_summary.service import (
    EMPTY_HISTORY_CODE,
    TranscriptMessage,
    summarize_transcript,
)
from packages.incident_summary.settings import (
    IncidentSummarySettings,
    get_incident_summary_settings,
)

if TYPE_CHECKING:
    from slack_sdk import WebClient

    from integrations.slack.provider import SlackPlatformProvider

logger = structlog.get_logger()

_DOMAIN = "incident_summary"
_SINCE_UNITS = {"m": 60, "h": 3600, "d": 86400}

# Slack renders its own "mrkdwn", not standard/GitHub Markdown: headers (``#``)
# and ``**bold**`` show up as literal text. Steer the model toward Slack-safe
# formatting so the ephemeral summary renders correctly.
_SLACK_FORMAT_INSTRUCTIONS = (
    "Format the summary using Slack mrkdwn, NOT standard Markdown. "
    "Rules: use *single asterisks* for bold (never **double**); use _underscores_ "
    "for italics; do NOT use Markdown headings (#, ##, ###) -- make section titles "
    "a bold line instead (e.g. *Key events*); start bullet lines with '• '; "
    "separate sections with a blank line. Keep links as plain URLs."
)


def register_commands(provider: SlackPlatformProvider) -> None:
    """Register the ``/sre incident summarize`` subcommand with the provider.

    The command works with no arguments (using safe defaults) as well as with
    ``--since``/``--limit``; a ``fallback_handler`` handles the no-argument
    invocation so the provider does not show help instead of running.

    Args:
        provider: Slack platform provider instance.
    """

    def _dispatch(payload: CommandPayload, parsed_args: dict[str, Any]) -> CommandResponse:
        return handle_summarize_command(payload, parsed_args, provider.client)

    def _dispatch_default(payload: CommandPayload) -> CommandResponse:
        return handle_summarize_command(payload, {}, provider.client)

    provider.register_command(
        command="summarize",
        handler=_dispatch,
        parent="sre.incident",
        description=("Summarize what has happened in this channel so far for someone joining the incident"),
        description_key=f"{_DOMAIN}.description",
        usage_hint="[--since 2h] [--limit 100]",
        examples=["", "--since 2h --limit 100"],
        example_keys=[f"{_DOMAIN}.examples.default", f"{_DOMAIN}.examples.since"],
        arguments=[
            Argument(
                name="--since",
                type=ArgumentType.STRING,
                required=False,
                description=("How far back to summarize, e.g. 30m, 2h, 1d (defaults to the start of the incident channel)"),
            ),
            Argument(
                name="--limit",
                type=ArgumentType.INTEGER,
                required=False,
                description="Maximum number of messages to include",
            ),
        ],
        fallback_handler=_dispatch_default,
    )


def handle_summarize_command(
    payload: CommandPayload,
    parsed_args: dict[str, Any],
    client: WebClient | None,
) -> CommandResponse:
    """Handle ``/sre incident summarize`` and return an ephemeral summary.

    Follows the five-step handler discipline: parse (framework) -> typed
    values -> gather inputs + one service call -> ``OperationResult`` ->
    render. All responses are ephemeral so the summary is only shown to the
    invoking responder.

    Args:
        payload: Command payload from the Slack platform provider.
        parsed_args: Parsed ``--since``/``--limit`` arguments (empty for the
            no-argument invocation). When ``--since`` is omitted the summary
            covers the whole incident, starting from channel creation.
        client: Slack Web API client, or ``None`` before startup.

    Returns:
        An ephemeral ``CommandResponse`` carrying the summary, an
        empty-history notice, or a generic error message.
    """
    locale = payload.user_locale or "en-US"
    log = logger.bind(
        command="incident_summarize",
        user_id=payload.user_id,
        channel_id=payload.channel_id,
    )

    if client is None or not payload.channel_id:
        log.warning("incident_summary_no_client_or_channel")
        return _error_response(locale)

    settings = get_incident_summary_settings()

    limit = _resolve_limit(parsed_args.get("--limit"), settings)
    oldest = _resolve_oldest(parsed_args.get("--since"))
    if oldest is None:
        # No explicit window: summarize the whole incident from when the
        # channel (incident) was created.
        oldest = _resolve_channel_start(client, payload.channel_id, settings, log)

    messages = _fetch_transcript(client, payload.channel_id, limit=limit, oldest=oldest, log=log)

    result = asyncio.run(summarize_transcript(messages, instructions=_SLACK_FORMAT_INSTRUCTIONS))

    if result.is_success:
        header = t(f"{_DOMAIN}.result.header", locale, "🧾 Incident summary")
        body = _to_slack_mrkdwn(result.data or "")
        return CommandResponse(message=f"{header}\n\n{body}", ephemeral=True)

    if result.error_code == EMPTY_HISTORY_CODE:
        msg = t(
            f"{_DOMAIN}.result.empty_history",
            locale,
            "There's nothing to summarize yet in this channel.",
        )
        return CommandResponse(message=msg, ephemeral=True)

    log.warning(
        "incident_summary_service_error",
        status=result.status,
        error=result.message,
    )
    return _error_response(locale)


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
        log.warning("incident_summary_history_fetch_failed", error=str(exc))
        return []

    raw_messages = response.get("messages") or []
    name_cache: dict[str, str] = {}
    messages: list[TranscriptMessage] = []

    # conversations_history returns newest-first; summarize chronologically.
    for raw in reversed(raw_messages):
        text = (raw.get("text") or "").strip()
        user_id = raw.get("user")
        if not text or not user_id:
            continue
        author = _resolve_display_name(client, user_id, name_cache, log)
        messages.append(TranscriptMessage(author=author, text=text))

    log.info(
        "incident_summary_history_fetched",
        raw_count=len(raw_messages),
        kept_count=len(messages),
    )
    return messages


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
    except Exception as exc:  # noqa: BLE001 - a missing name must not fail the summary
        log.warning("incident_summary_user_lookup_failed", user_id=user_id, error=str(exc))

    cache[user_id] = name
    return name


def _resolve_limit(raw: Any, settings: IncidentSummarySettings) -> int:
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


def _resolve_oldest(raw: Any) -> float | None:
    """Convert ``--since`` into a Unix ``oldest`` timestamp.

    Returns ``None`` when ``--since`` is absent or invalid so the caller can
    default to the incident's start (channel creation time).
    """
    seconds = _parse_since_seconds(raw)
    if seconds is None:
        return None
    return time.time() - seconds


def _resolve_channel_start(
    client: WebClient,
    channel_id: str,
    settings: IncidentSummarySettings,
    log: structlog.stdlib.BoundLogger,
) -> float:
    """Return the channel's creation time as a Unix ``oldest`` timestamp.

    Falls back to the configured default window if the channel info lookup
    fails, so a missing ``channels:read``/``groups:read`` scope degrades
    gracefully instead of failing the summary.
    """
    try:
        info = client.conversations_info(channel=channel_id)
        created = (info.get("channel") or {}).get("created")
        if created is not None:
            return float(created)
    except Exception as exc:  # noqa: BLE001 - degrade to default window on any API error
        log.warning("incident_summary_channel_info_failed", error=str(exc))

    return time.time() - settings.DEFAULT_SINCE_HOURS * _SINCE_UNITS["h"]


def _parse_since_seconds(raw: Any) -> int | None:
    """Parse a ``--since`` duration (e.g. ``30m``, ``2h``, ``1d``) into seconds.

    A bare number is treated as hours. Returns ``None`` for missing or invalid
    input so the caller applies the configured default.
    """
    if not raw:
        return None

    value = str(raw).strip().lower()
    unit = value[-1] if value else ""
    if unit in _SINCE_UNITS:
        number = value[:-1]
    else:
        unit = "h"
        number = value

    try:
        amount = int(number)
    except TypeError, ValueError:
        return None
    if amount <= 0:
        return None
    return amount * _SINCE_UNITS[unit]


def _to_slack_mrkdwn(text: str) -> str:
    """Normalize model output into valid Slack ``mrkdwn``.

    Models occasionally emit standard/GitHub Markdown despite instructions.
    Slack does not render ``**bold**``, ``__bold__``, or ``#`` headings, and it
    shows literal ``**`` characters. This is a defensive, format-only pass:

    - ``**bold**``/``__bold__`` -> ``*bold*`` (Slack bold).
    - Markdown headings (``#``..``######``) -> a bold line.
    - Bullet markers (``-``, ``*``, ``+``, one or more ``•``) -> a single
      ``• `` prefix, collapsing duplicates like ``• •``.

    Content is never altered -- only formatting markers.
    """
    # **bold** / __bold__ -> *bold* first, so heading/bullet handling below
    # never has to reason about double-marker runs.
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)

    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]

        # Markdown heading -> bold line (drop the leading #s).
        heading = re.match(r"^#{1,6}\s+(.*)$", stripped)
        if heading:
            content = heading.group(1).strip().strip("*")
            lines.append(f"*{content}*" if content else "")
            continue

        # Collapse any run of bullet markers (-, *, +, •) into a single "• ".
        bullet = re.match(r"^(?:[-+\u2022]\s*)+(.*)$", stripped)
        if bullet:
            content = bullet.group(1).strip()
            stripped = f"\u2022 {content}" if content else "\u2022"

        lines.append(f"{indent}{stripped}")

    return "\n".join(lines).strip()


def _error_response(locale: str) -> CommandResponse:
    """Build the generic ephemeral error response."""
    msg = t(
        f"{_DOMAIN}.result.error",
        locale,
        "❌ Couldn't generate a summary right now. Please try again shortly.",
    )
    return CommandResponse(message=msg, ephemeral=True)
