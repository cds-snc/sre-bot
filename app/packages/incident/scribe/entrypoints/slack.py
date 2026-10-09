"""Slack entry point for the incident scribe subdomain: commands, block actions and view submissions.

Registers ``/sre incident draft``, ``/sre incident summarize`` and
``/sre incident status-update`` as children of ``sre.incident``, and the
status-updates modal's block-action and view-submission listeners. Each command
handler translates its arguments, makes one call to the platform-agnostic
``packages.incident.scribe.service`` and renders the outcome ephemerally.
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

Status update: opens the incident's status-updates modal, private to the
invoker. A loading view opens at once with the command's trigger id (it expires
after about three seconds), then the view is updated to the pending draft, a
no-draft notice or a localized error. Nothing is posted to the channel.

The Draft button is a native Bolt listener registered through the command
registrar. It acks, makes one call to the status-update service and updates the
modal with the result or a localized error. The service calls back just before
a model call so the modal shows a drafting state only then. For a security or
unknown-flag incident the service refuses until the responder confirms, so the
modal shows a confirmation view whose Confirm and draft button calls the
service again with confirmation; Cancel is the view's close button. Slack API
failures are logged and never raised; nothing is posted to the channel.

The Write it myself button runs the same service in manual mode (no model call,
no security gate) and replaces the modal with the review form for the returned
draft. A Draft whose model call failed comes back as a manual draft and lands
on the same form with a notice. A hand-written draft's form has no Redraft
section.

The Review button replaces the modal in place with the review form. Submitting
it acks with field errors for blank fields, or with a saving view; the approval
and the copy-ready rendering then run in one event loop and the modal is updated
by view id to the copy-ready text or an error.

The reopened copy-ready view's toggle marks the update published or not
published (the button carries the target state), then re-renders the stored
record in place. It writes only the update's state; nothing is posted.

The review form's Redraft button sends the reviewer's instructions and current
form values to the redraft service. Blank instructions, a refusal or a failure
re-render the form with a notice (the previous draft is kept); a redraft shows
the new draft's form. Only the modal is updated.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any

import structlog

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from contracts.slack.models import Argument, ArgumentType, CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplySender
from packages.incident.core.api import StatusUpdate
from packages.incident.scribe import providers
from packages.incident.scribe.domain import CopyReadyText, StatusUpdateDraftOutcome, StatusUpdateEdit, StatusUpdateOutcomeKind
from packages.incident.scribe.entrypoints.slack_views import (
    CONFIRM_ACTION_ID,
    DRAFT_ACTION_ID,
    DRAFT_DOMAIN,
    HISTORY_ACTION_ID,
    OPEN_ACTION_ID,
    PUBLISHED_ACTION_ID,
    REDRAFT_ACTION_ID,
    REVIEW_ACTION_ID,
    REVIEW_CALLBACK_ID,
    SLACK_FORMAT_INSTRUCTIONS,
    STATUS_UPDATE_DOMAIN,
    SUMMARY_DOMAIN,
    WRITE_ACTION_ID,
    build_copy_ready_view,
    build_draft_error_view,
    build_drafting_view,
    build_no_new_information_wording,
    build_overview_view,
    build_profile_labels,
    build_published_error_view,
    build_redrafting_view,
    build_result_view,
    build_review_error_view,
    build_review_field_errors,
    build_review_view,
    build_saving_view,
    build_security_confirmation_view,
    draft_error_response,
    draft_success_response,
    manual_fallback_notice,
    mrkdwn_blocks,
    notify_working,
    parse_redraft_form,
    parse_review_submission,
    redraft_notice,
    render_error,
    status_error_text,
    status_t,
    status_update_open_failed,
    status_update_view,
    summary_error_response,
    summary_success_response,
    summary_text,
    to_slack_mrkdwn,
)
from packages.incident.scribe.service import (
    EMPTY_HISTORY_CODE,
    draft_incident_document_from_conversation,
    summarize_incident_conversation,
)
from packages.incident.scribe.status_update import (
    DRAFT_UNPARSEABLE_CODE,
    draft_status_update,
    get_status_update_overview,
    redraft_status_update,
)
from packages.incident.scribe.status_update_approval import (
    approve_status_update,
    get_draft_for_review,
    validate_approval_edit,
)
from packages.incident.scribe.status_update_history import get_approved_update, set_published

logger = structlog.get_logger()

_SINCE_UNITS = {"m": 60, "h": 3600, "d": 86400}


def register(registrar: SlackCommandRegistrar) -> None:
    """Register the scribe commands, the status-updates modal listeners and the approval submission.

    Registers the ``/sre incident draft``, ``summarize`` and ``status-update``
    subcommands, then the Draft, Confirm and draft, Write it myself, Review,
    Open, Back, published toggle and Redraft listeners and the approval
    submission. Draft and summarize work with no arguments (draft: the whole
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

    def _dispatch_status_update(payload: CommandPayload) -> CommandResponse:
        return handle_status_update_command(payload, {}, registrar.reply)

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
    registrar.register_command(
        command="status-update",
        handler=_dispatch_status_update,
        parent="sre.incident",
        description="Open this incident's status updates and show the pending draft",
        description_key=f"{STATUS_UPDATE_DOMAIN}.description",
        usage_hint="",
        examples=[""],
        example_keys=[f"{STATUS_UPDATE_DOMAIN}.examples.default"],
    )
    registrar.register_block_action(DRAFT_ACTION_ID, handle_draft_action)
    registrar.register_block_action(CONFIRM_ACTION_ID, handle_draft_confirmed_action)
    registrar.register_block_action(WRITE_ACTION_ID, handle_write_action)
    registrar.register_block_action(REVIEW_ACTION_ID, handle_review_action)
    registrar.register_block_action(OPEN_ACTION_ID, handle_open_action)
    registrar.register_block_action(HISTORY_ACTION_ID, handle_history_action)
    registrar.register_block_action(PUBLISHED_ACTION_ID, handle_published_action)
    registrar.register_block_action(REDRAFT_ACTION_ID, handle_redraft_action)
    registrar.register_view_submission(REVIEW_CALLBACK_ID, handle_review_submission)


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
            instructions=SLACK_FORMAT_INSTRUCTIONS,
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
        return status_update_open_failed(locale)

    private_metadata = json.dumps({"channel_id": payload.channel_id, "locale": locale})
    opened = reply.open_view(
        trigger_id=trigger_id,
        view=status_update_view(
            locale, private_metadata, mrkdwn_blocks(status_t("loading", locale, "Loading the status update...")), close=False
        ),
    )
    if not opened.is_success or opened.data is None:
        log.warning("incident_status_update_open_failed", error=opened.message, error_code=opened.error_code)
        return status_update_open_failed(locale)
    view_id = opened.data

    overview = get_status_update_overview(payload.channel_id)
    if overview.is_success and overview.data is not None:
        view = build_overview_view(overview.data, locale, private_metadata)
    else:
        log.warning(
            "incident_status_update_failed", status=overview.status, error_code=overview.error_code, error=overview.message
        )
        view = status_update_view(
            locale, private_metadata, mrkdwn_blocks(status_error_text(overview.error_code, locale)), close=True
        )

    updated = reply.update_view(view_id=view_id, view=view)
    if not updated.is_success:
        log.warning("incident_status_update_view_update_failed", error=updated.message, error_code=updated.error_code)
    return CommandResponse(message="", ephemeral=True)


def handle_draft_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of the Draft button in the status-updates modal.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; carries the view id, hash and private metadata.
        client: Bolt Slack web client.
    """
    ack()
    _run_draft(body, client, security_confirmed=False)


def handle_draft_confirmed_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of Confirm and draft in the security confirmation view.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; carries the view id, hash and private metadata.
        client: Bolt Slack web client.
    """
    ack()
    _run_draft(body, client, security_confirmed=True)


def handle_write_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of Write it myself in the status-updates modal.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; carries the view id, hash and private metadata.
        client: Bolt Slack web client.
    """
    ack()
    _run_draft(body, client, security_confirmed=False, manual=True)


class _ModalCursor:
    """The modal's view id and latest hash; updates log Slack errors and never raise."""

    def __init__(self, client: Any, view_id: str, view_hash: str | None, log: structlog.stdlib.BoundLogger) -> None:
        self._client = client
        self._view_id = view_id
        self._hash = view_hash
        self._log = log

    def update(self, view: dict[str, Any], *, failure_event: str) -> None:
        """Replace the modal's view and remember the new hash; log ``failure_event`` on a Slack error."""
        try:
            if self._hash:
                response = self._client.views_update(view_id=self._view_id, hash=self._hash, view=view)
            else:
                response = self._client.views_update(view_id=self._view_id, view=view)
            self._hash = _response_hash(response)
        except Exception:
            self._log.warning(failure_event, exc_info=True)


def _run_draft(body: dict[str, Any], client: Any, *, security_confirmed: bool, manual: bool = False) -> None:
    """Draft through the service and update the modal with the confirmation, result, review form or error."""
    view = body.get("view") or {}
    view_id = str(view.get("id", ""))
    user_id = str((body.get("user") or {}).get("id", ""))
    metadata = _parse_metadata(view.get("private_metadata"))
    channel_id = str(metadata.get("channel_id", ""))
    locale = str(metadata.get("locale") or "en-US")
    private_metadata = json.dumps({"channel_id": channel_id, "locale": locale})
    log = logger.bind(
        action="incident_status_update_draft",
        user_id=user_id,
        channel_id=channel_id,
        view_id=view_id,
        confirmed=security_confirmed,
        manual=manual,
    )
    modal = _ModalCursor(client, view_id, view.get("hash"), log)

    def show_drafting() -> None:
        modal.update(build_drafting_view(locale, private_metadata), failure_event="incident_status_update_drafting_update_failed")

    result = asyncio.run(
        draft_status_update(
            channel_id,
            author=user_id,
            wording=build_no_new_information_wording(),
            on_started=show_drafting,
            security_confirmed=security_confirmed,
            manual=manual,
        )
    )
    if result.is_success and result.data is not None and (manual or result.data.kind is StatusUpdateOutcomeKind.MANUAL):
        result_view = _manual_review_view(result.data, locale, channel_id, manual=manual)
        failure_event = "incident_status_update_review_update_failed"
    elif result.is_success and result.data is not None:
        result_view = build_result_view(result.data, locale, private_metadata)
        failure_event = "incident_status_update_result_update_failed"
    elif result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED:
        log.info("incident_status_update_security_confirmation_shown")
        result_view = build_security_confirmation_view(locale, private_metadata)
        failure_event = "incident_status_update_confirmation_update_failed"
    else:
        log.warning("incident_status_update_draft_failed", status=result.status, error_code=result.error_code)
        result_view = build_draft_error_view(result.error_code, locale, private_metadata)
        failure_event = "incident_status_update_result_update_failed"
    modal.update(result_view, failure_event=failure_event)


def _manual_review_view(outcome: StatusUpdateDraftOutcome, locale: str, channel_id: str, *, manual: bool) -> dict[str, Any]:
    """The review form for a draft the responder writes; only a failed Draft explains why."""
    update = outcome.update
    hand_written = outcome.kind is StatusUpdateOutcomeKind.MANUAL
    review_metadata = json.dumps(
        {"channel_id": channel_id, "locale": locale, "incident_id": update.incident_id, "sequence": update.sequence}
    )
    notice = manual_fallback_notice(locale) if hand_written and not manual else None
    return build_review_view(update, locale, review_metadata, notice, with_redraft=not hand_written)


def handle_review_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of the Review button: replace the modal in place with the review form.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; the button value names the incident and sequence.
        client: Bolt Slack web client.
    """
    ack()
    view = body.get("view") or {}
    view_id = str(view.get("id", ""))
    metadata = _parse_metadata(view.get("private_metadata"))
    channel_id = str(metadata.get("channel_id", ""))
    locale = str(metadata.get("locale") or "en-US")
    private_metadata = json.dumps({"channel_id": channel_id, "locale": locale})
    log = logger.bind(
        action="incident_status_update_review",
        user_id=str((body.get("user") or {}).get("id", "")),
        channel_id=channel_id,
        view_id=view_id,
    )
    target = _parse_metadata(((body.get("actions") or [{}])[0]).get("value"))
    incident_id = str(target.get("incident_id", ""))
    sequence = target.get("sequence")

    result = asyncio.run(get_draft_for_review(incident_id, sequence)) if isinstance(sequence, int) else None
    if result is not None and result.is_success and result.data is not None:
        review_metadata = json.dumps(
            {"channel_id": channel_id, "locale": locale, "incident_id": incident_id, "sequence": sequence}
        )
        next_view = build_review_view(result.data, locale, review_metadata)
    else:
        error_code = result.error_code if result is not None else None
        log.warning("incident_status_update_review_failed", error_code=error_code)
        next_view = build_review_error_view(error_code, locale, private_metadata)
    _ModalCursor(client, view_id, view.get("hash"), log).update(
        next_view, failure_event="incident_status_update_review_update_failed"
    )


def handle_open_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of Open on an approved update: replace the modal in place with its copy-ready text.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; the button value names the incident and sequence.
        client: Bolt Slack web client.
    """
    ack()
    view = body.get("view") or {}
    view_id = str(view.get("id", ""))
    metadata = _parse_metadata(view.get("private_metadata"))
    locale = str(metadata.get("locale") or "en-US")
    private_metadata = json.dumps({"channel_id": str(metadata.get("channel_id", "")), "locale": locale})
    log = logger.bind(action="incident_status_update_open", user_id=str((body.get("user") or {}).get("id", "")), view_id=view_id)
    target = _parse_metadata(((body.get("actions") or [{}])[0]).get("value"))
    incident_id = str(target.get("incident_id", ""))
    sequence = target.get("sequence")

    result = asyncio.run(_read_and_publish(incident_id, sequence)) if isinstance(sequence, int) else None
    if result is not None and result.is_success and result.data is not None:
        update, copy = result.data
        next_view = build_copy_ready_view(copy, locale, private_metadata, update=update)
    else:
        error_code = result.error_code if result is not None else None
        log.warning("incident_status_update_open_failed", error_code=error_code)
        next_view = build_draft_error_view(error_code, locale, private_metadata)
    _ModalCursor(client, view_id, view.get("hash"), log).update(
        next_view, failure_event="incident_status_update_open_update_failed"
    )


def handle_history_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of Back: replace the modal in place with the incident's status-updates list.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; the button value names the channel.
        client: Bolt Slack web client.
    """
    ack()
    view = body.get("view") or {}
    view_id = str(view.get("id", ""))
    metadata = _parse_metadata(view.get("private_metadata"))
    locale = str(metadata.get("locale") or "en-US")
    channel_id = str(_parse_metadata(((body.get("actions") or [{}])[0]).get("value")).get("channel_id", ""))
    private_metadata = json.dumps({"channel_id": channel_id, "locale": locale})
    log = logger.bind(
        action="incident_status_update_history",
        user_id=str((body.get("user") or {}).get("id", "")),
        channel_id=channel_id,
        view_id=view_id,
    )

    result = get_status_update_overview(channel_id)
    if result.is_success and result.data is not None:
        next_view = build_overview_view(result.data, locale, private_metadata)
    else:
        log.warning("incident_status_update_history_failed", status=result.status, error_code=result.error_code)
        next_view = build_draft_error_view(result.error_code, locale, private_metadata)
    _ModalCursor(client, view_id, view.get("hash"), log).update(
        next_view, failure_event="incident_status_update_history_update_failed"
    )


def handle_published_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of the published toggle: set the target state, then show the record's copy-ready text.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; the button value names the incident, sequence and target state.
        client: Bolt Slack web client.
    """
    ack()
    view = body.get("view") or {}
    view_id = str(view.get("id", ""))
    user_id = str((body.get("user") or {}).get("id", ""))
    metadata = _parse_metadata(view.get("private_metadata"))
    locale = str(metadata.get("locale") or "en-US")
    private_metadata = json.dumps({"channel_id": str(metadata.get("channel_id", "")), "locale": locale})
    log = logger.bind(action="incident_status_update_published", user_id=user_id, view_id=view_id)
    target = _parse_metadata(((body.get("actions") or [{}])[0]).get("value"))
    incident_id = str(target.get("incident_id", ""))
    sequence = target.get("sequence")
    published = target.get("published")

    result = None
    if isinstance(sequence, int) and isinstance(published, bool):
        result = asyncio.run(_toggle_and_publish(incident_id, sequence, published=published, actor=user_id))
    if result is not None and result.is_success and result.data is not None:
        update, copy = result.data
        next_view = build_copy_ready_view(copy, locale, private_metadata, update=update)
    else:
        error_code = result.error_code if result is not None else None
        log.warning("incident_status_update_published_failed", error_code=error_code)
        next_view = build_published_error_view(error_code, locale, private_metadata)
    _ModalCursor(client, view_id, view.get("hash"), log).update(
        next_view, failure_event="incident_status_update_published_update_failed"
    )


def handle_redraft_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of Redraft in the review form: redraft from the instructions, then update the modal in place.

    Blank instructions re-render the form with a notice and call no service. A
    redraft shows the new draft's form; a refusal or failure keeps the previous
    draft and re-renders the form from the reviewer's values with their
    instructions; a conflict shows the review conflict view.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; carries the view id, hash, review metadata and form state.
        client: Bolt Slack web client.
    """
    ack()
    view = body.get("view") or {}
    view_id = str(view.get("id", ""))
    user_id = str((body.get("user") or {}).get("id", ""))
    metadata = _parse_metadata(view.get("private_metadata"))
    channel_id = str(metadata.get("channel_id", ""))
    locale = str(metadata.get("locale") or "en-US")
    incident_id = str(metadata.get("incident_id", ""))
    sequence = int(metadata.get("sequence") or 0)
    instructions, security_confirmed = parse_redraft_form(view)
    edit = parse_review_submission(view)
    log = logger.bind(action="incident_status_update_redraft", user_id=user_id, channel_id=channel_id, view_id=view_id)
    modal = _ModalCursor(client, view_id, view.get("hash"), log)

    def review_metadata(target: int) -> str:
        return json.dumps({"channel_id": channel_id, "locale": locale, "incident_id": incident_id, "sequence": target})

    def show_redrafting() -> None:
        modal.update(
            build_redrafting_view(locale, review_metadata(sequence)),
            failure_event="incident_status_update_redrafting_update_failed",
        )

    async def run() -> tuple[OperationResult[StatusUpdate] | None, OperationResult[StatusUpdate] | None]:
        """Redraft unless blank; read the stored draft only when it is the model's base or a re-render needs it."""
        stored = await get_draft_for_review(incident_id, sequence) if edit is None else None
        current = edit or (_as_edit(stored.data) if stored is not None and stored.data is not None else None)
        if not instructions.strip() or current is None:
            return None, stored or await get_draft_for_review(incident_id, sequence)
        result = await redraft_status_update(
            channel_id,
            sequence,
            instructions=instructions,
            current=current,
            author=user_id,
            security_confirmed=security_confirmed,
            on_started=show_redrafting,
        )
        if result.is_success or result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT:
            return result, stored
        return result, stored or await get_draft_for_review(incident_id, sequence)

    result, stored = asyncio.run(run())
    if result is not None and result.is_success and result.data is not None:
        notice = redraft_notice("redrafted_note", locale)
        next_view = build_review_view(result.data, locale, review_metadata(result.data.sequence), notice=notice)
    elif (result is not None and result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT) or stored is None or stored.data is None:
        failed = stored if stored is not None and not stored.is_success else result
        error_code = failed.error_code if failed is not None else None
        log.warning("incident_status_update_redraft_failed", error_code=error_code)
        next_view = build_review_error_view(error_code, locale, review_metadata(sequence))
    else:
        form = stored.data if edit is None else replace(stored.data, stage=edit.stage, en=edit.en, fr=edit.fr)
        if result is None:
            log.info("incident_status_update_redraft_blank")
            next_view = build_review_view(form, locale, review_metadata(sequence), notice=redraft_notice("redraft_blank", locale))
        else:
            log.warning("incident_status_update_redraft_failed", status=result.status, error_code=result.error_code)
            refused = result.error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED
            next_view = build_review_view(
                form,
                locale,
                review_metadata(sequence),
                notice=redraft_notice(_redraft_failure_key(result.error_code), locale),
                instructions=instructions,
                security_confirm=refused,
            )
    modal.update(next_view, failure_event="incident_status_update_redraft_update_failed")


def _as_edit(update: StatusUpdate) -> StatusUpdateEdit:
    """The stored draft's stage and fields as the model's base."""
    return StatusUpdateEdit(stage=update.stage, en=update.en, fr=update.fr)


def _redraft_failure_key(error_code: str | None) -> str:
    """Map a redraft refusal or failure onto its notice key; the previous draft was kept."""
    if error_code == ErrorCode.SECURITY_CONFIRMATION_REQUIRED:
        return "redraft_security"
    if error_code == DRAFT_UNPARSEABLE_CODE:
        return "redraft_unparseable"
    return "redraft_failed"


async def _read_and_publish(incident_id: str, sequence: int) -> OperationResult[tuple[StatusUpdate, CopyReadyText]]:
    """Read the approved update, then render it as copy-ready text in one event loop."""
    return await _render_record(await get_approved_update(incident_id, sequence))


async def _toggle_and_publish(
    incident_id: str, sequence: int, *, published: bool, actor: str
) -> OperationResult[tuple[StatusUpdate, CopyReadyText]]:
    """Set the update's published state, then render the stored record as copy-ready text in one event loop."""
    return await _render_record(await set_published(incident_id, sequence, published=published, actor=actor))


async def _render_record(read: OperationResult[StatusUpdate]) -> OperationResult[tuple[StatusUpdate, CopyReadyText]]:
    """Render a read or toggled record through the status page publisher; a failed ``read`` is passed on."""
    if not read.is_success or read.data is None:
        return OperationResult.error(read.status, message=read.message or "read failed", error_code=read.error_code)
    published = await providers.get_status_page_publisher().publish(
        read.data, labels_en=build_profile_labels("en-US"), labels_fr=build_profile_labels("fr-FR")
    )
    if not published.is_success or published.data is None:
        return OperationResult.error(
            published.status, message=published.message or "publish failed", error_code=published.error_code
        )
    return OperationResult.success(data=(read.data, published.data))


def handle_review_submission(ack: Callable[..., Any], body: dict[str, Any], client: Any) -> None:
    """Handle the review modal's submission: validate, approve, then show the copy-ready text.

    Blank fields and an unreadable stage ack with field errors and call nothing.
    Otherwise the ack replaces the form with the saving view inside Slack's
    window, and the modal is updated by view id (no hash, the ack changed it).

    Args:
        ack: Bolt ack callable, called exactly once.
        body: View-submission payload; carries the view, its state and the submitting user.
        client: Bolt Slack web client.
    """
    view = body.get("view") or {}
    view_id = str(view.get("id", ""))
    approver = str((body.get("user") or {}).get("id", ""))
    metadata = _parse_metadata(view.get("private_metadata"))
    locale = str(metadata.get("locale") or "en-US")
    private_metadata = json.dumps(
        {
            "channel_id": str(metadata.get("channel_id", "")),
            "locale": locale,
            "incident_id": str(metadata.get("incident_id", "")),
            "sequence": metadata.get("sequence"),
        }
    )
    edit = parse_review_submission(view)
    blank = ("stage",) if edit is None else validate_approval_edit(edit)
    if edit is None or blank:
        ack(response_action="errors", errors=build_review_field_errors(blank, locale))
        return
    ack(response_action="update", view=build_saving_view(locale, private_metadata))

    log = logger.bind(action="incident_status_update_approval", user_id=approver, view_id=view_id)
    result = asyncio.run(
        _approve_and_publish(str(metadata.get("incident_id", "")), int(metadata.get("sequence") or 0), approver, edit)
    )
    if result.is_success and result.data is not None:
        next_view = build_copy_ready_view(result.data, locale, private_metadata)
    else:
        log.warning("incident_status_update_approval_failed", status=result.status, error_code=result.error_code)
        next_view = build_review_error_view(result.error_code, locale, private_metadata)
    _ModalCursor(client, view_id, None, log).update(next_view, failure_event="incident_status_update_approval_update_failed")


async def _approve_and_publish(
    incident_id: str, sequence: int, approver: str, edit: StatusUpdateEdit
) -> OperationResult[CopyReadyText]:
    """Approve the draft, then render the approved record as copy-ready text.

    One coroutine so a submission needs one event loop, and an async Bolt
    listener could await it directly. A refused approval is returned as a
    failure without publishing.
    """
    approved = await approve_status_update(incident_id, sequence, approver=approver, edit=edit)
    if not approved.is_success or approved.data is None:
        return OperationResult.error(
            approved.status, message=approved.message or "approval failed", error_code=approved.error_code
        )
    return await providers.get_status_page_publisher().publish(
        approved.data, labels_en=build_profile_labels("en-US"), labels_fr=build_profile_labels("fr-FR")
    )


def _parse_metadata(raw: Any) -> dict[str, Any]:
    """Decode the view's private metadata; empty when missing or malformed."""
    try:
        parsed = json.loads(raw) if raw else {}
    except TypeError, ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _response_hash(response: Any) -> str | None:
    """Return the new view hash from a views.update response, when present."""
    try:
        value = response["view"]["hash"]
    except KeyError, TypeError, IndexError:
        return None
    return value if isinstance(value, str) else None
