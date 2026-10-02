"""Slack platform adapter for the incident_summary package.

Registers ``/sre incident summarize`` as a child of ``sre.incident`` and
turns recent channel history into an ephemeral catch-up summary. The adapter
owns the Slack-specific input and output: it translates ``--since`` and
``--limit``, makes one call to the platform-agnostic
``packages.incident_summary.service`` and renders the result as Slack mrkdwn.

The service reads the conversation's transcript through the incident core's
``IncidentTranscriptReader`` interface; no history fetch, name resolution or
window resolution happens here.
"""

import asyncio
import re
from datetime import timedelta
from typing import Any

import structlog

from contracts.slack.models import Argument, ArgumentType, CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from infrastructure.i18n import t
from packages.incident_summary.service import EMPTY_HISTORY_CODE, summarize_incident_conversation

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
    "a bold line instead (e.g. *Current status*); start bullet lines with '• '; "
    "separate sections with a blank line. Keep links as plain URLs."
)


def register_commands(registrar: SlackCommandRegistrar) -> None:
    """Register the ``/sre incident summarize`` subcommand with the registrar.

    The command works with no arguments (using safe defaults) as well as with
    ``--since``/``--limit``; a ``fallback_handler`` handles the no-argument
    invocation so the runtime does not show help instead of running.

    Args:
        registrar: Slack command registrar.
    """

    def _dispatch(payload: CommandPayload, parsed_args: dict[str, Any]) -> CommandResponse:
        return handle_summarize_command(payload, parsed_args)

    def _dispatch_default(payload: CommandPayload) -> CommandResponse:
        return handle_summarize_command(payload, {})

    registrar.register_command(
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
) -> CommandResponse:
    """Handle ``/sre incident summarize`` and return an ephemeral summary.

    Follows the five-step handler discipline: parse (framework) -> typed
    values -> one service call -> ``OperationResult`` -> render. All responses are ephemeral so the summary is only shown to the
    invoking responder.

    Args:
        payload: Command payload from the Slack platform provider.
        parsed_args: Parsed ``--since``/``--limit`` arguments (empty for the
            no-argument invocation). When ``--since`` is omitted the summary
            covers the whole incident, starting from channel creation.

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

    if not payload.channel_id:
        log.warning("incident_summary_no_channel")
        return _error_response(locale)

    result = asyncio.run(
        summarize_incident_conversation(
            payload.channel_id,
            since=_parse_since(parsed_args.get("--since")),
            limit=_parse_limit(parsed_args.get("--limit")),
            instructions=_SLACK_FORMAT_INSTRUCTIONS,
        )
    )

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


def _parse_limit(raw: Any) -> int | None:
    """Coerce the ``--limit`` value into an integer; ``None`` when absent or unreadable."""
    if raw is None:
        return None
    try:
        return int(raw)
    except TypeError, ValueError:
        return None


def _parse_since(raw: Any) -> timedelta | None:
    """Convert ``--since`` into a duration.

    Returns ``None`` when ``--since`` is absent or invalid so the service
    defaults to the incident's start (channel creation time).
    """
    seconds = _parse_since_seconds(raw)
    if seconds is None:
        return None
    return timedelta(seconds=seconds)


def _parse_since_seconds(raw: Any) -> int | None:
    """Parse a ``--since`` duration (e.g. ``30m``, ``2h``, ``1d``) into seconds.

    A bare number is treated as hours. Returns ``None`` for missing or invalid
    input so the service applies its default window.
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
