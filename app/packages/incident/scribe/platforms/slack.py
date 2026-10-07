"""Slack platform adapter for the incident scribe subdomain.

Registers ``/sre incident draft``, ``/sre incident summarize`` and
``/sre incident status-update`` as children of ``sre.incident``. Each handler translates its arguments, makes one call to
the platform-agnostic ``packages.incident.scribe.service`` and renders the
outcome ephemerally.

Draft: the service finds the incident report, reads the channel's transcript,
answers each heading's template instructions from it and writes the result into
a new draft document. The in-request progress notice goes through the
registrar's reply interface, posted when the service signals that the report
was found and the slow work is starting.

Summarize: the service reads the conversation's transcript through the incident
core's ``IncidentTranscriptReader`` interface and the result is rendered as
Slack mrkdwn; no history fetch, name resolution or window resolution happens
here.

Status update: opens the incident's status-updates modal, private to the
invoker. A loading view opens at once with the command's trigger id (it expires
after about three seconds), then the view is updated to the pending draft, a
no-draft notice or a localized error. Nothing is posted to the channel.

No Slack SDK is imported here.
"""

import asyncio
import json
import re
from datetime import timedelta
from types import MappingProxyType
from typing import Any

import structlog

from contracts.operations.codes import ErrorCode
from contracts.slack.models import Argument, ArgumentType, CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplySender
from infrastructure.i18n import t
from packages.incident.core.api import StatusUpdate, StatusUpdateStage
from packages.incident.scribe.comms_profile import ProfileLabels, render_profile
from packages.incident.scribe.domain import DraftedDocument
from packages.incident.scribe.service import (
    DOCUMENT_UNREADABLE_CODE,
    EMPTY_HISTORY_CODE,
    NO_ANSWERS_CODE,
    NO_DOCUMENT_CODE,
    draft_incident_document_from_conversation,
    summarize_incident_conversation,
)
from packages.incident.scribe.status_update import get_pending_status_update

logger = structlog.get_logger()

_DRAFT_DOMAIN = "incident_draft"
_SUMMARY_DOMAIN = "incident_summary"
_STATUS_UPDATE_DOMAIN = "incident_status_update"
_SLACK_TEXT_LIMIT = 3000
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
    """Register the ``/sre incident draft``, ``summarize`` and ``status-update`` subcommands.

    Both commands work with no arguments (draft: the whole incident history;
    summarize: safe defaults) as well as with their options; a
    ``fallback_handler`` handles the no-argument invocation so the runtime does
    not show help instead of running.

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

    def _dispatch_status_update(payload: CommandPayload) -> CommandResponse:
        return handle_status_update_command(payload, {}, registrar.reply)

    registrar.register_command(
        command="draft",
        handler=_dispatch_draft,
        parent="sre.incident",
        description=("Draft a filled-in copy of the incident document from this channel's history"),
        description_key=f"{_DRAFT_DOMAIN}.description",
        usage_hint="[--limit 500]",
        examples=["", "--limit 200"],
        example_keys=[f"{_DRAFT_DOMAIN}.examples.default", f"{_DRAFT_DOMAIN}.examples.limit"],
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
        description_key=f"{_SUMMARY_DOMAIN}.description",
        usage_hint="[--since 2h] [--limit 100]",
        examples=["", "--since 2h --limit 100"],
        example_keys=[f"{_SUMMARY_DOMAIN}.examples.default", f"{_SUMMARY_DOMAIN}.examples.since"],
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
    registrar.register_command(
        command="status-update",
        handler=_dispatch_status_update,
        parent="sre.incident",
        description="Open this incident's status updates and show the pending draft",
        description_key=f"{_STATUS_UPDATE_DOMAIN}.description",
        usage_hint="",
        examples=[""],
        example_keys=[f"{_STATUS_UPDATE_DOMAIN}.examples.default"],
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
        return _draft_error_response(locale)

    channel_id = payload.channel_id

    # Everything past the report lookup is slow -- fetching the channel, one AI
    # call, then several Google Docs round trips. Bolt has already acked, so
    # without this notice the invoker watches nothing happen for a minute. The
    # service calls it once the report is found, so a channel with no report
    # gets no notice.
    def _on_started() -> None:
        _notify_working(reply, channel_id, payload, locale, log)

    result = asyncio.run(
        draft_incident_document_from_conversation(
            channel_id,
            limit=_parse_limit(parsed_args.get("--limit")),
            on_started=_on_started,
        )
    )

    if result.is_success:
        return _success_response(result.data, locale)
    return _render_error(result.error_code, locale, log, result)


def _notify_working(
    reply: SlackReplySender,
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
        f"{_DRAFT_DOMAIN}.result.working",
        locale,
        "🤖 Reading this channel and drafting the incident report — this usually takes up to a minute. "
        "I'll post a link here when it's ready.",
    )
    posted = reply.post_ephemeral(channel_id=channel_id, user_id=payload.user_id, text=text)
    if not posted.is_success:
        log.warning("incident_draft_progress_notice_failed", error=posted.message, error_code=posted.error_code)


def _success_response(outcome: DraftedDocument | None, locale: str) -> CommandResponse:
    """Render the one-line confirmation, linking the new draft."""
    if outcome is None:
        return _draft_error_response(locale)

    url = f"https://docs.google.com/document/d/{outcome.document_id}/edit"
    if outcome.partial:
        # Worth saying: later sections are missing because the response ran out,
        # not because the channel had nothing to say about them.
        message = t(
            f"{_DRAFT_DOMAIN}.result.partial",
            locale,
            "Created an AI-generated <{{url}}|draft incident report> from this channel, but the "
            "response ran long and later sections are missing — re-run to fill them in. Copy over "
            "whatever's useful into the original incident doc created when the incident opened.",
            url=url,
        )
        return CommandResponse(message=message.replace("{{url}}", url), ephemeral=True)

    message = t(
        f"{_DRAFT_DOMAIN}.result.header",
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
    if error_code == NO_DOCUMENT_CODE:
        msg = t(
            f"{_DRAFT_DOMAIN}.result.no_document",
            locale,
            "I couldn't find an incident document bookmarked in this channel.",
        )
        return CommandResponse(message=msg, ephemeral=True)
    if error_code == DOCUMENT_UNREADABLE_CODE:
        msg = t(
            f"{_DRAFT_DOMAIN}.result.unreadable",
            locale,
            "I couldn't read any sections from the incident document.",
        )
        return CommandResponse(message=msg, ephemeral=True)
    if error_code == EMPTY_HISTORY_CODE:
        msg = t(
            f"{_DRAFT_DOMAIN}.result.empty_history",
            locale,
            "There's no channel history to draft from yet.",
        )
        return CommandResponse(message=msg, ephemeral=True)
    if error_code == NO_ANSWERS_CODE:
        msg = t(
            f"{_DRAFT_DOMAIN}.result.no_answers",
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
    return _draft_error_response(locale)


def _parse_limit(raw: Any) -> int | None:
    """Coerce the ``--limit`` value into an integer; ``None`` when absent or unreadable."""
    if raw is None:
        return None
    try:
        return int(raw)
    except TypeError, ValueError:
        return None


def _draft_error_response(locale: str) -> CommandResponse:
    """Build the generic ephemeral error response."""
    msg = t(
        f"{_DRAFT_DOMAIN}.result.error",
        locale,
        "❌ Couldn't create the draft document right now. Please try again shortly.",
    )
    return CommandResponse(message=msg, ephemeral=True)


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
        return _summary_error_response(locale)

    result = asyncio.run(
        summarize_incident_conversation(
            payload.channel_id,
            since=_parse_since(parsed_args.get("--since")),
            limit=_parse_limit(parsed_args.get("--limit")),
            instructions=_SLACK_FORMAT_INSTRUCTIONS,
        )
    )

    if result.is_success:
        header = t(f"{_SUMMARY_DOMAIN}.result.header", locale, "🧾 Incident summary")
        body = _to_slack_mrkdwn(result.data or "")
        return CommandResponse(message=f"{header}\n\n{body}", ephemeral=True)

    if result.error_code == EMPTY_HISTORY_CODE:
        msg = t(
            f"{_SUMMARY_DOMAIN}.result.empty_history",
            locale,
            "There's nothing to summarize yet in this channel.",
        )
        return CommandResponse(message=msg, ephemeral=True)

    log.warning(
        "incident_summary_service_error",
        status=result.status,
        error=result.message,
    )
    return _summary_error_response(locale)


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
        # "*" counts only when whitespace follows, so a "*bold title*" line is kept.
        bullet = re.match(r"^(?:[-+\u2022]\s*|\*\s+)+(.*)$", stripped)
        if bullet:
            content = bullet.group(1).strip()
            stripped = f"\u2022 {content}" if content else "\u2022"

        lines.append(f"{indent}{stripped}")

    return "\n".join(lines).strip()


def _summary_error_response(locale: str) -> CommandResponse:
    """Build the generic ephemeral error response."""
    msg = t(
        f"{_SUMMARY_DOMAIN}.result.error",
        locale,
        "❌ Couldn't generate a summary right now. Please try again shortly.",
    )
    return CommandResponse(message=msg, ephemeral=True)


def handle_status_update_command(
    payload: CommandPayload,
    parsed_args: dict[str, Any],
    reply: SlackReplySender,
) -> CommandResponse:
    """Handle ``/sre incident status-update`` by opening the status-updates modal.

    The loading view is opened first with the trigger id, before any lookup,
    because the trigger id expires after about three seconds and the incident
    lookup can take longer. The view is then updated to the pending draft, the
    no-draft notice or a localized error with a Close button. Opening never
    drafts, and nothing is posted to the channel.

    Args:
        payload: Command payload; ``platform_metadata["trigger_id"]`` opens the view.
        parsed_args: Unused; the command takes no arguments.
        reply: Interface used to open and update the modal.

    Returns:
        An empty ephemeral response once the modal opened; a localized
        ephemeral notice when there is no trigger id or the view could not
        open, since no view exists to show it in.
    """
    locale = payload.user_locale or "en-US"
    log = logger.bind(command="incident_status_update", user_id=payload.user_id, channel_id=payload.channel_id)

    trigger_id = str(payload.platform_metadata.get("trigger_id", ""))
    if not trigger_id or not payload.channel_id:
        log.warning("incident_status_update_no_trigger_or_channel")
        return _status_update_open_failed(locale)

    private_metadata = json.dumps({"channel_id": payload.channel_id, "locale": locale})
    opened = reply.open_view(
        trigger_id=trigger_id,
        view=_status_update_view(
            locale, private_metadata, _mrkdwn_blocks(_status_t("loading", locale, "Loading the status update...")), close=False
        ),
    )
    if not opened.is_success or opened.data is None:
        log.warning("incident_status_update_open_failed", error=opened.message, error_code=opened.error_code)
        return _status_update_open_failed(locale)
    view_id = opened.data

    pending = get_pending_status_update(payload.channel_id)
    if pending.is_success and pending.data is not None:
        blocks = _pending_blocks(pending.data)
    elif pending.is_success:
        blocks = _mrkdwn_blocks(_status_t("no_pending", locale, "There is no status update draft for this incident yet."))
    else:
        log.warning("incident_status_update_failed", status=pending.status, error_code=pending.error_code, error=pending.message)
        blocks = _mrkdwn_blocks(_status_error_text(pending.error_code, locale))

    updated = reply.update_view(view_id=view_id, view=_status_update_view(locale, private_metadata, blocks, close=True))
    if not updated.is_success:
        log.warning("incident_status_update_view_update_failed", error=updated.message, error_code=updated.error_code)
    return CommandResponse(message="", ephemeral=True)


def _status_t(key: str, locale: str, fallback: str) -> str:
    return t(f"{_STATUS_UPDATE_DOMAIN}.{key}", locale, fallback)


def _status_error_text(error_code: str | None, locale: str) -> str:
    """Map a lookup or store error code onto its localized in-modal message."""
    if error_code == ErrorCode.NOT_AN_INCIDENT:
        return _status_t(
            "not_an_incident", locale, "This channel is not an incident channel, so there are no status updates to show."
        )
    if error_code == ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION:
        return _status_t(
            "ambiguous", locale, "More than one incident uses this channel, so I can't tell which status updates to show."
        )
    return _status_t("error", locale, "Couldn't load the status update right now. Please try again shortly.")


def _status_update_open_failed(locale: str) -> CommandResponse:
    message = _status_t("open_failed", locale, "Couldn't open the status updates right now. Please try again shortly.")
    return CommandResponse(message=message, ephemeral=True)


def _status_update_view(locale: str, private_metadata: str, blocks: list[dict[str, Any]], *, close: bool) -> dict[str, Any]:
    """Build the status-updates modal; the loading view has no Close button."""
    view: dict[str, Any] = {
        "type": "modal",
        "title": {"type": "plain_text", "text": _status_t("title", locale, "Status updates")},
        "private_metadata": private_metadata,
        "blocks": blocks,
    }
    if close:
        view["close"] = {"type": "plain_text", "text": _status_t("close", locale, "Close")}
    return view


def _mrkdwn_blocks(text: str) -> list[dict[str, Any]]:
    """Split ``text`` into section blocks, each under Slack's text limit."""
    chunks = [text[i : i + _SLACK_TEXT_LIMIT] for i in range(0, len(text), _SLACK_TEXT_LIMIT)] or [""]
    return [{"type": "section", "text": {"type": "mrkdwn", "text": chunk}} for chunk in chunks]


def _pending_blocks(update: StatusUpdate) -> list[dict[str, Any]]:
    """Render the draft in English then French with the default comms profile.

    Both languages use fixed locale lookups, so both render whatever the
    invoker's locale is.
    """
    blocks: list[dict[str, Any]] = []
    for locale, language, text in (("en-US", "en", update.en), ("fr-FR", "fr", update.fr)):
        heading = _status_t(f"language.{language}", locale, "English" if language == "en" else "French")
        profile = render_profile(text, update.stage, update.next_update_at, build_profile_labels(locale))
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": heading}})
        blocks.extend(_mrkdwn_blocks(profile))
    return blocks


def build_profile_labels(locale: str) -> ProfileLabels:
    """Build the comms profile labels for one language from the catalogue."""
    fr = locale.startswith("fr")
    return ProfileLabels(
        stage=_status_t("label.stage", locale, "Étape" if fr else "Stage"),
        affected_service=_status_t("label.affected_service", locale, "Service touché" if fr else "Affected service"),
        impact=_status_t("label.impact", locale, "Incidence" if fr else "Impact"),
        current_action=_status_t("label.current_action", locale, "Mesure en cours" if fr else "Current action"),
        workaround=_status_t("label.workaround", locale, "Solution de contournement" if fr else "Workaround"),
        next_update=_status_t("label.next_update", locale, "Prochaine mise à jour" if fr else "Next update"),
        time_suffix=_status_t("time_suffix", locale, "HE" if fr else "ET"),
        stage_names=MappingProxyType(
            {stage: _status_t(f"stage.{stage.value}", locale, stage.value.capitalize()) for stage in StatusUpdateStage}
        ),
    )
