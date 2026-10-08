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
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.comms_profile import ProfileLabels, format_profile_time, render_profile
from packages.incident.scribe.domain import (
    CopyReadyText,
    DraftedDocument,
    NoNewInformationWording,
    StatusUpdateDraftOutcome,
    StatusUpdateEdit,
    StatusUpdateOutcomeKind,
    StatusUpdateOverview,
)
from packages.incident.scribe.service import (
    DOCUMENT_UNREADABLE_CODE,
    EMPTY_HISTORY_CODE,
    NO_ANSWERS_CODE,
    NO_DOCUMENT_CODE,
    draft_incident_document_from_conversation,
    summarize_incident_conversation,
)
from packages.incident.scribe.status_update import DRAFT_UNPARSEABLE_CODE, get_status_update_overview

logger = structlog.get_logger()

_DRAFT_DOMAIN = "incident_draft"
_SUMMARY_DOMAIN = "incident_summary"
_STATUS_UPDATE_DOMAIN = "incident_status_update"
_SLACK_TEXT_LIMIT = 3000
DRAFT_ACTION_ID = "incident.scribe.status_update.draft"
CONFIRM_ACTION_ID = "incident.scribe.status_update.draft_confirmed"
REVIEW_ACTION_ID = "incident.scribe.status_update.review"
REVIEW_CALLBACK_ID = "incident.scribe.status_update.approve"
OPEN_ACTION_ID = "incident.scribe.status_update.open"
HISTORY_ACTION_ID = "incident.scribe.status_update.history"
_APPROVED_ROW_CAP = 50
_TEXT_FIELDS = ("affected_service", "impact", "current_action", "workaround")
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

    overview = get_status_update_overview(payload.channel_id)
    if overview.is_success and overview.data is not None:
        view = build_overview_view(overview.data, locale, private_metadata)
    else:
        log.warning(
            "incident_status_update_failed", status=overview.status, error_code=overview.error_code, error=overview.message
        )
        view = _status_update_view(
            locale, private_metadata, _mrkdwn_blocks(_status_error_text(overview.error_code, locale)), close=True
        )

    updated = reply.update_view(view_id=view_id, view=view)
    if not updated.is_success:
        log.warning("incident_status_update_view_update_failed", error=updated.message, error_code=updated.error_code)
    return CommandResponse(message="", ephemeral=True)


def _status_t(key: str, locale: str, fallback: str) -> str:
    return t(f"{_STATUS_UPDATE_DOMAIN}.{key}", locale, fallback)


def _status_error_text(error_code: str | None, locale: str) -> str:
    """Map a lookup, store or drafting error code onto its localized in-modal message."""
    if error_code == ErrorCode.EMPTY_HISTORY:
        return _status_t("empty_history", locale, "There is no channel history to draft a status update from yet.")
    if error_code == DRAFT_UNPARSEABLE_CODE:
        return _status_t("unparseable", locale, "I couldn't turn the model's answer into a status update. Please try again.")
    if error_code == ErrorCode.STATUS_UPDATE_CONFLICT:
        return _status_t("conflict", locale, "Another status update was saved at the same time. Please try again.")
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
        "title": {
            "type": "plain_text",
            "text": _status_t("title", locale, "Mises à jour de statut" if locale.startswith("fr") else "Status updates"),
        },
        "private_metadata": private_metadata,
        "blocks": blocks,
    }
    if close:
        view["close"] = {
            "type": "plain_text",
            "text": _status_t("close", locale, "Fermer" if locale.startswith("fr") else "Close"),
        }
    return view


def _mrkdwn_blocks(text: str) -> list[dict[str, Any]]:
    """Split ``text`` into section blocks, each under Slack's text limit."""
    chunks = [text[i : i + _SLACK_TEXT_LIMIT] for i in range(0, len(text), _SLACK_TEXT_LIMIT)] or [""]
    return [{"type": "section", "text": {"type": "mrkdwn", "text": chunk}} for chunk in chunks]


def _language_heading(language: str) -> str:
    """Name a profile language in that language ("English", "Français"), matching the catalogue."""
    locale, fallback = ("en-US", "English") if language == "en" else ("fr-FR", "Français")
    return _status_t(f"language.{language}", locale, fallback)


def _pending_blocks(update: StatusUpdate) -> list[dict[str, Any]]:
    """Render the draft in English then French with the default comms profile.

    Both languages use fixed locale lookups, so both render whatever the
    invoker's locale is.
    """
    blocks: list[dict[str, Any]] = []
    for locale, language, text in (("en-US", "en", update.en), ("fr-FR", "fr", update.fr)):
        heading = _language_heading(language)
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


def _draft_button_block(locale: str, update: StatusUpdate | None, *, with_draft: bool) -> dict[str, Any]:
    """Build the actions block holding the Draft button and, for a shown draft, the Review button."""
    elements: list[dict[str, Any]] = []
    if with_draft:
        elements.append(
            {
                "type": "button",
                "action_id": DRAFT_ACTION_ID,
                "text": {"type": "plain_text", "text": _status_t("draft_button", locale, "Draft")},
                "style": "primary",
            }
        )
    if update is not None:
        elements.append(
            {
                "type": "button",
                "action_id": REVIEW_ACTION_ID,
                "text": {
                    "type": "plain_text",
                    "text": _status_t("review_button", locale, "Réviser" if locale.startswith("fr") else "Review"),
                },
                "value": json.dumps({"incident_id": update.incident_id, "sequence": update.sequence}),
            }
        )
    return {"type": "actions", "block_id": "draft_button", "elements": elements}


def build_security_confirmation_view(locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the modal asking the responder to confirm drafting for a security or unknown-flag incident.

    The Confirm and draft button re-runs the draft with confirmation; the
    view's Cancel close button closes the modal without a model call.
    """
    fr = locale.startswith("fr")
    text = _status_t(
        "security_confirmation",
        locale,
        "Cet incident est, ou pourrait être, un incident de sécurité. La rédaction envoie le contenu du canal de "
        "l'incident et des communications au modèle d'IA. Voulez-vous continuer?"
        if fr
        else "This incident is, or may be, a security incident. Drafting sends the incident channel and comms content "
        "to the AI model. Do you want to continue?",
    )
    confirm_block = {
        "type": "actions",
        "block_id": "draft_confirm_button",
        "elements": [
            {
                "type": "button",
                "action_id": CONFIRM_ACTION_ID,
                "text": {
                    "type": "plain_text",
                    "text": _status_t("confirm_button", locale, "Confirmer et rédiger" if fr else "Confirm and draft"),
                },
                "style": "primary",
            }
        ],
    }
    view = _status_update_view(locale, private_metadata, [*_mrkdwn_blocks(text), confirm_block], close=False)
    view["close"] = {"type": "plain_text", "text": _status_t("cancel", locale, "Annuler" if fr else "Cancel")}
    return view


def _stage_line(update: StatusUpdate, locale: str) -> str:
    """Return ``*Stage* - time - approved by <@U> - Published`` for an approved or published update."""
    fr = locale.startswith("fr")
    labels = build_profile_labels(locale)
    parts = [f"*{labels.stage_names[update.stage]}*", format_profile_time(update.approved_at or update.created_at, labels)]
    if update.approver:
        by = _status_t("row.approved_by", locale, "approuvée par" if fr else "approved by")
        parts.append(f"{by} <@{update.approver}>")
    if update.state is StatusUpdateState.PUBLISHED:
        parts.append(_status_t("row.published", locale, "Publiée" if fr else "Published"))
    else:
        parts.append(_status_t("row.not_published", locale, "Non publiée" if fr else "Not published"))
    return " - ".join(parts)


def _approved_blocks(approved: tuple[StatusUpdate, ...], locale: str) -> list[dict[str, Any]]:
    """Render the approved-updates header, then one Open row per update (newest 50), an empty state or a cap note."""
    fr = locale.startswith("fr")
    header = _status_t("history_header", locale, "Mises à jour approuvées" if fr else "Approved updates")
    blocks: list[dict[str, Any]] = [
        {"type": "header", "block_id": "approved_updates", "text": {"type": "plain_text", "text": header}}
    ]
    if not approved:
        empty = _status_t(
            "history_empty",
            locale,
            "Aucune mise à jour de statut n'a encore été approuvée pour cet incident."
            if fr
            else "No status update has been approved for this incident yet.",
        )
        blocks.append({"type": "section", "block_id": "approved_updates_empty", "text": {"type": "mrkdwn", "text": empty}})
        return blocks
    open_text = _status_t("open_button", locale, "Ouvrir" if fr else "Open")
    for update in approved[:_APPROVED_ROW_CAP]:
        blocks.append(
            {
                "type": "section",
                "block_id": f"approved_update.{update.sequence}",
                "text": {"type": "mrkdwn", "text": _stage_line(update, locale)},
                "accessory": {
                    "type": "button",
                    "action_id": OPEN_ACTION_ID,
                    "text": {"type": "plain_text", "text": open_text},
                    "value": json.dumps({"incident_id": update.incident_id, "sequence": update.sequence}),
                },
            }
        )
    if len(approved) > _APPROVED_ROW_CAP:
        note = _status_t(
            "history_truncated",
            locale,
            "Affichage des 50 dernières mises à jour approuvées." if fr else "Showing the latest 50 approved updates.",
        )
        blocks.append(
            {"type": "context", "block_id": "approved_updates_truncated", "elements": [{"type": "mrkdwn", "text": note}]}
        )
    return blocks


def build_overview_view(overview: StatusUpdateOverview, locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the status-updates modal: the pending draft part, then the approved-updates list."""
    if overview.pending is not None:
        blocks = [*_pending_blocks(overview.pending), _draft_button_block(locale, overview.pending, with_draft=True)]
    else:
        blocks = [
            *_mrkdwn_blocks(_status_t("no_pending", locale, "There is no status update draft for this incident yet.")),
            _draft_button_block(locale, None, with_draft=True),
        ]
    blocks.extend(_approved_blocks(overview.approved, locale))
    return _status_update_view(locale, private_metadata, blocks, close=True)


def build_drafting_view(locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the modal shown while the draft is being written; no buttons."""
    blocks = _mrkdwn_blocks(_status_t("drafting", locale, "Drafting the status update. This usually takes up to a minute..."))
    return _status_update_view(locale, private_metadata, blocks, close=False)


def build_result_view(outcome: StatusUpdateDraftOutcome, locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the modal showing the drafted, carried-forward or pending update in EN and FR."""
    blocks = [*_pending_blocks(outcome.update), _draft_button_block(locale, outcome.update, with_draft=False)]
    if outcome.kind == StatusUpdateOutcomeKind.CARRIED_FORWARD:
        note = _status_t("carried_forward", locale, "Nothing new since the last update, so it was repeated as a new draft.")
    elif outcome.kind == StatusUpdateOutcomeKind.PENDING:
        note = _status_t("pending", locale, "This draft already covers the latest activity, so no new draft was written.")
    else:
        note = _status_t("drafted", locale, "Drafted from the incident channel.")
    return _status_update_view(locale, private_metadata, [*_mrkdwn_blocks(note), *blocks], close=True)


def build_draft_error_view(error_code: str | None, locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the modal showing a localized drafting error with a Close button."""
    return _status_update_view(locale, private_metadata, _mrkdwn_blocks(_status_error_text(error_code, locale)), close=True)


def build_review_error_view(error_code: str | None, locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the modal showing a localized review or approval error with a Close button.

    Differs from ``build_draft_error_view`` in the wording of a conflict (the
    draft changed or was approved elsewhere) and in the stage-below-floor refusal.
    """
    if error_code == ErrorCode.STATUS_UPDATE_STAGE_BELOW_FLOOR:
        text = _status_t(
            "stage_below_floor",
            locale,
            "L'étape ne peut pas précéder celle de la dernière mise à jour approuvée. Rouvrez la révision et choisissez une étape ultérieure."
            if locale.startswith("fr")
            else "The stage cannot be earlier than the latest approved update's stage. Reopen the review and pick a later stage.",
        )
    elif error_code == ErrorCode.STATUS_UPDATE_CONFLICT:
        text = _status_t(
            "review_conflict",
            locale,
            "Ce brouillon a changé ou a été approuvé ailleurs. Rouvrez les mises à jour de statut pour voir la dernière version."
            if locale.startswith("fr")
            else "This draft changed or was approved elsewhere. Reopen the status updates to see the latest version.",
        )
    else:
        text = _status_error_text(error_code, locale)
    return _status_update_view(locale, private_metadata, _mrkdwn_blocks(text), close=True)


def _review_input(block_id: str, label: str, element: dict[str, Any]) -> dict[str, Any]:
    return {"type": "input", "block_id": block_id, "label": {"type": "plain_text", "text": label}, "element": element}


def build_review_view(update: StatusUpdate, locale: str, private_metadata: str, notice: str | None = None) -> dict[str, Any]:
    """Build the review modal: the stage select and the four EN and four FR fields, prefilled from the draft.

    Field inputs are optional so Slack never blocks a blank field itself; the
    submission listener validates and names the blank ones.
    """
    fr = locale.startswith("fr")
    stage_names = build_profile_labels(locale).stage_names
    options = [{"text": {"type": "plain_text", "text": stage_names[stage]}, "value": stage.value} for stage in StatusUpdateStage]
    blocks = _mrkdwn_blocks(notice) if notice else []
    blocks.append(
        _review_input(
            "stage",
            _status_t("label.stage", locale, "Étape" if fr else "Stage"),
            {
                "type": "static_select",
                "action_id": "stage",
                "options": options,
                "initial_option": next(option for option in options if option["value"] == update.stage.value),
            },
        )
    )
    for profile_locale, language, text in (("en-US", "en", update.en), ("fr-FR", "fr", update.fr)):
        labels = build_profile_labels(profile_locale)
        heading = _language_heading(language)
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": heading}})
        for name in _TEXT_FIELDS:
            element = {
                "type": "plain_text_input",
                "action_id": "text",
                "multiline": True,
                "initial_value": getattr(text, name),
            }
            block = _review_input(f"{language}.{name}", getattr(labels, name), element)
            block["optional"] = True
            blocks.append(block)
    view = _status_update_view(locale, private_metadata, blocks, close=False)
    view["title"] = {
        "type": "plain_text",
        "text": _status_t("review_title", locale, "Réviser la mise à jour" if fr else "Review update"),
    }
    view["callback_id"] = REVIEW_CALLBACK_ID
    view["submit"] = {"type": "plain_text", "text": _status_t("approve_button", locale, "Approuver" if fr else "Approve")}
    view["close"] = {"type": "plain_text", "text": _status_t("cancel", locale, "Annuler" if fr else "Cancel")}
    return view


def parse_review_submission(view: dict[str, Any]) -> StatusUpdateEdit | None:
    """Read the submitted stage and fields back into an edit; ``None`` when the stage is missing or unknown.

    Text is not trimmed and a cleared field (Slack sends null) reads as ``""``,
    so ``validate_approval_edit`` is the single blank-handling path.
    """
    values: dict[str, Any] = (view.get("state") or {}).get("values") or {}
    selected = ((values.get("stage") or {}).get("stage") or {}).get("selected_option") or {}
    try:
        stage = StatusUpdateStage(str(selected.get("value", "")))
    except ValueError:
        return None

    def read(language: str) -> StatusUpdateText:
        return StatusUpdateText(
            **{name: ((values.get(f"{language}.{name}") or {}).get("text") or {}).get("value") or "" for name in _TEXT_FIELDS}
        )

    return StatusUpdateEdit(stage=stage, en=read("en"), fr=read("fr"))


def build_review_field_errors(block_ids: tuple[str, ...], locale: str) -> dict[str, str]:
    """Map each rejected block id to the localized blank-field message for ``ack(response_action="errors")``."""
    message = _status_t("field_blank", locale, "Entrez une valeur." if locale.startswith("fr") else "Enter a value.")
    return dict.fromkeys(block_ids, message)


def build_saving_view(locale: str, private_metadata: str) -> dict[str, Any]:
    """Build the modal shown while the approval is saved; no buttons and no submit."""
    blocks = _mrkdwn_blocks(
        _status_t("saving", locale, "Enregistrement de l'approbation..." if locale.startswith("fr") else "Saving the approval...")
    )
    return _status_update_view(locale, private_metadata, blocks, close=False)


def build_copy_ready_view(
    copy: CopyReadyText, locale: str, private_metadata: str, update: StatusUpdate | None = None
) -> dict[str, Any]:
    """Build the modal showing the approved text, one preformatted block per language, with Close.

    With ``update`` (a reopened approved update) a status line comes first and a
    Back button, valued with the channel id from the metadata, comes last.
    """
    note = _status_t(
        "approved_note",
        locale,
        "Approuvé. Relisez, puis copiez dans le canal de votre produit. Rien n'a été publié."
        if locale.startswith("fr")
        else "Approved. Proofread, then copy into your product's channel. Nothing was posted.",
    )
    blocks = _mrkdwn_blocks(note)
    for language, text in (("en", copy.en), ("fr", copy.fr)):
        heading = _language_heading(language)
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": heading}})
        preformatted = {"type": "rich_text_preformatted", "elements": [{"type": "text", "text": text}]}
        blocks.append({"type": "rich_text", "elements": [preformatted]})
    if update is not None:
        status = {
            "type": "section",
            "block_id": "approved_status",
            "text": {"type": "mrkdwn", "text": _stage_line(update, locale)},
        }
        channel_id = json.loads(private_metadata).get("channel_id", "")
        back = {
            "type": "button",
            "action_id": HISTORY_ACTION_ID,
            "text": {
                "type": "plain_text",
                "text": _status_t("back_button", locale, "Retour" if locale.startswith("fr") else "Back"),
            },
            "value": json.dumps({"channel_id": channel_id}),
        }
        blocks = [status, *blocks, {"type": "actions", "block_id": "history_button", "elements": [back]}]
    return _status_update_view(locale, private_metadata, blocks, close=True)


def build_no_new_information_wording() -> NoNewInformationWording:
    """Build the carried-forward current-action wording in both languages."""
    return NoNewInformationWording(
        en=_status_t("no_new_information", "en-US", "No new information since the last update."),
        fr=_status_t("no_new_information", "fr-FR", "Aucune nouvelle information depuis la dernière mise à jour."),
    )
