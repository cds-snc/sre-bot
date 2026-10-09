"""Slack entry point for the incident scribe subdomain: the draft and summarize commands.

Registers ``/sre incident draft`` and ``/sre incident summarize`` as children
of ``sre.incident``. Each command
handler translates its arguments, makes one call to the platform-agnostic
``features.incident.scribe.service`` and renders the outcome ephemerally.
Wording and views come from ``entrypoints/slack_views.py``, the only module
that translates.

Draft: the service finds the incident report, reads the channel's transcript,
answers each heading's template instructions from it and writes the result into
a new draft document. The in-request progress notice goes through the
registrar's reply interface, posted when the service signals that the report
was found and the slow work is starting.

Summarize: the service reads the conversation's transcript through the incident
core's ``IncidentTranscriptReader`` interface and the result is rendered as
Slack mrkdwn; no history fetch, name resolution or window resolution happens
here.

"""

import asyncio
from datetime import timedelta
from typing import Any

import structlog

from contracts.slack.models import Argument, ArgumentType, CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplySender
from features.incident.scribe.entrypoints.slack_views import (
    DRAFT_DOMAIN,
    SUMMARY_DOMAIN,
    draft_error_response,
    draft_success_response,
    notify_working,
    render_error,
    summary_error_response,
    summary_success_response,
    summary_text,
    to_slack_mrkdwn,
)
from features.incident.scribe.service import (
    EMPTY_HISTORY_CODE,
    draft_incident_document_from_conversation,
    summarize_incident_conversation,
)

logger = structlog.get_logger()

_SINCE_UNITS = {"m": 60, "h": 3600, "d": 86400}


def register(registrar: SlackCommandRegistrar) -> None:
    """Register the ``/sre incident draft`` and ``summarize`` subcommands.

    Both work with no arguments (draft: the whole
    incident history; summarize: safe defaults) as well as with their options;
    a ``fallback_handler`` handles the no-argument invocation so the runtime
    does not show help instead of running.

    Args:
        registrar: Slack command registrar.
    """

    def _dispatch_draft(payload: CommandPayload, parsed_args: dict[str, Any]) -> CommandResponse:
        return handle_draft_command(payload, parsed_args, registrar.reply)

    def _dispatch_draft_default(payload: CommandPayload) -> CommandResponse:
        return handle_draft_command(payload, {}, registrar.reply)

    def _dispatch_summarize(payload: CommandPayload, parsed_args: dict[str, Any]) -> CommandResponse:
        return handle_summarize_command(payload, parsed_args)

    def _dispatch_summarize_default(payload: CommandPayload) -> CommandResponse:
        return handle_summarize_command(payload, {})

    registrar.register_command(
        command="draft",
        handler=_dispatch_draft,
        parent="sre.incident",
        description=("Draft a filled-in copy of the incident document from this channel's history"),
        description_key=f"{DRAFT_DOMAIN}.description",
        usage_hint="[--limit 500]",
        examples=["", "--limit 200"],
        example_keys=[f"{DRAFT_DOMAIN}.examples.default", f"{DRAFT_DOMAIN}.examples.limit"],
        arguments=[
            Argument(
                name="--limit",
                type=ArgumentType.INTEGER,
                required=False,
                description="Maximum number of channel messages to draft from",
            ),
        ],
        fallback_handler=_dispatch_draft_default,
    )
    registrar.register_command(
        command="summarize",
        handler=_dispatch_summarize,
        parent="sre.incident",
        description=("Summarize what has happened in this channel so far for someone joining the incident"),
        description_key=f"{SUMMARY_DOMAIN}.description",
        usage_hint="[--since 2h] [--limit 100]",
        examples=["", "--since 2h --limit 100"],
        example_keys=[f"{SUMMARY_DOMAIN}.examples.default", f"{SUMMARY_DOMAIN}.examples.since"],
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
        fallback_handler=_dispatch_summarize_default,
    )


def handle_draft_command(
    payload: CommandPayload,
    parsed_args: dict[str, Any],
    reply: SlackReplySender,
) -> CommandResponse:
    """Handle ``/sre incident draft`` and report the outcome ephemerally.

    Follows the five-step handler discipline: parse (framework) -> typed
    values -> one service call -> ``OperationResult`` -> render. All responses
    are ephemeral so only the invoking responder sees them; the drafted content
    lands in a new document.

    Args:
        payload: Command payload from the Slack platform provider.
        parsed_args: Parsed ``--limit`` argument (empty for the no-argument
            invocation). History always starts at the channel's creation so the
            draft covers the whole incident.
        reply: Interface used to post the progress notice.

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

    if not payload.channel_id:
        log.warning("incident_draft_no_channel")
        return draft_error_response(locale)

    channel_id = payload.channel_id

    # Everything past the report lookup is slow -- fetching the channel, one AI
    # call, then several Google Docs round trips. Bolt has already acked, so
    # without this notice the invoker watches nothing happen for a minute. The
    # service calls it once the report is found, so a channel with no report
    # gets no notice.
    def _on_started() -> None:
        notify_working(reply, channel_id, payload, locale, log)

    result = asyncio.run(
        draft_incident_document_from_conversation(
            channel_id,
            limit=_parse_limit(parsed_args.get("--limit")),
            on_started=_on_started,
        )
    )

    if result.is_success:
        return draft_success_response(result.data, locale)
    return render_error(result.error_code, locale, log, result)


def _parse_limit(raw: Any) -> int | None:
    """Coerce the ``--limit`` value into an integer; ``None`` when absent or unreadable."""
    if raw is None:
        return None
    try:
        return int(raw)
    except TypeError, ValueError:
        return None


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
        return summary_error_response(locale)

    result = asyncio.run(
        summarize_incident_conversation(
            payload.channel_id,
            since=_parse_since(parsed_args.get("--since")),
            limit=_parse_limit(parsed_args.get("--limit")),
        )
    )

    if result.is_success:
        return summary_success_response(to_slack_mrkdwn(result.data or ""), locale)

    if result.error_code == EMPTY_HISTORY_CODE:
        msg = summary_text("result.empty_history", locale, "There's nothing to summarize yet in this channel.")
        return CommandResponse(message=msg, ephemeral=True)

    log.warning(
        "incident_summary_service_error",
        status=result.status,
        error=result.message,
    )
    return summary_error_response(locale)


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
