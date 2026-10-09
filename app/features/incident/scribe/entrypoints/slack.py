"""Slack entry point for the incident scribe subdomain: commands, block actions and view submissions.

Registers ``/sre incident draft``, ``/sre incident summarize`` and
``/sre incident status-update`` as children of ``sre.incident``, and the
status-updates modal's block-action and view-submission listeners. Each command
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

Status update: opens the incident's status-updates modal, private to the
invoker. A loading view opens at once with the command's trigger id (it expires
after about three seconds), then the view is updated to the pending draft, a
no-draft notice or a localized error. Nothing is posted to the channel.

The modal's buttons are native Bolt listeners registered through the command
registrar. Each acks, makes one call to a status-update service and updates the
modal in place with the result or a localized error. Slack API failures are
logged and never raised; nothing is posted to the channel.

The New update button, shown when no draft is pending, starts a draft by hand
(no model call, no security read) and replaces the modal with the review form
for it, or for a draft another responder started meanwhile.

The Review button replaces the modal in place with the review form. Submitting
it acks with field errors for blank fields, or with a saving view; the approval
and the copy-ready rendering then run in one event loop and the modal is updated
by view id to the copy-ready text or an error.

The review form carries the AI section (Draft with AI, optional instructions)
only when text generation is configured. Draft with AI sends the responder's
current form values and instructions to the generate service, which calls back
just before a model call so the modal shows a generating state only then. A
fill shows the new draft's form; nothing new carries the typed values forward
without a model call. For a security or unknown-flag incident the service
refuses until the responder checks the confirmation box the form then shows. A
refusal or failure re-renders the typed values with a notice (the previous
draft is kept). Only the modal is updated.

The reopened copy-ready view's toggle marks the update published or not
published (the button carries the target state), then re-renders the stored
record in place. It writes only the update's state; nothing is posted.

The review form's Save draft button stores the typed stage and fields as the
next draft and re-renders the form for it with a notice. A stale sequence shows
the conflict view; any other failure re-renders the typed values with a notice.
Only the modal is updated.
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, TypedDict

import structlog

from contracts.slack.models import Argument, ArgumentType, CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplySender
from features.incident.scribe.comms_profile import ProfileLabels
from features.incident.scribe.entrypoints.slack_views import (
    DRAFT_DOMAIN,
    GENERATE_ACTION_ID,
    HISTORY_ACTION_ID,
    NEW_ACTION_ID,
    OPEN_ACTION_ID,
    PUBLISHED_ACTION_ID,
    REVIEW_ACTION_ID,
    REVIEW_CALLBACK_ID,
    SAVE_ACTION_ID,
    STATUS_UPDATE_DOMAIN,
    SUMMARY_DOMAIN,
    build_copy_ready_view,
    build_draft_error_view,
    build_filled_form_view,
    build_generating_view,
    build_no_new_information_wording,
    build_overview_view,
    build_profile_labels,
    build_published_error_view,
    build_review_error_view,
    build_review_field_errors,
    build_review_view,
    build_saved_form_view,
    build_saving_view,
    draft_error_response,
    draft_success_response,
    mrkdwn_blocks,
    notify_working,
    parse_ai_form,
    parse_review_submission,
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
from features.incident.scribe.service import (
    EMPTY_HISTORY_CODE,
    draft_incident_document_from_conversation,
    summarize_incident_conversation,
)
from features.incident.scribe.status_update import get_status_update_overview
from features.incident.scribe.status_update_approval import approve_and_publish
from features.incident.scribe.status_update_form import (
    fill_status_update_form,
    open_status_update_form,
    save_status_update_form,
    start_status_update_form,
)
from features.incident.scribe.status_update_history import read_published, set_published_and_render

logger = structlog.get_logger()

_SINCE_UNITS = {"m": 60, "h": 3600, "d": 86400}


def register(registrar: SlackCommandRegistrar) -> None:
    """Register the scribe commands, the status-updates modal listeners and the approval submission.

    Registers the ``/sre incident draft``, ``summarize`` and ``status-update``
    subcommands, then the New update, Save draft, Draft with AI, Review, Open,
    Back and published toggle listeners and the approval submission. Draft and summarize work with no arguments (draft: the whole
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
    registrar.register_block_action(NEW_ACTION_ID, handle_new_update_action)
    registrar.register_block_action(SAVE_ACTION_ID, handle_save_action)
    registrar.register_block_action(GENERATE_ACTION_ID, handle_generate_action)
    registrar.register_block_action(REVIEW_ACTION_ID, handle_review_action)
    registrar.register_block_action(OPEN_ACTION_ID, handle_open_action)
    registrar.register_block_action(HISTORY_ACTION_ID, handle_history_action)
    registrar.register_block_action(PUBLISHED_ACTION_ID, handle_published_action)
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


def handle_new_update_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of New update in the status-updates modal: start a hand-written draft and show its form.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; carries the view id, hash and private metadata.
        client: Bolt Slack web client.
    """
    ack()
    action = _parse_action(body)
    log = action.bind("incident_status_update_new")

    result = start_status_update_form(action.channel_id, author=action.user_id)
    if result.is_success and result.data is not None:
        update = result.data.update
        metadata = action.review_metadata(update.incident_id, update.sequence)
        next_view = build_review_view(update, action.locale, metadata, with_ai=result.data.ai_available)
    else:
        log.warning("incident_status_update_new_failed", status=result.status, error_code=result.error_code)
        next_view = build_draft_error_view(result.error_code, action.locale, action.list_metadata())
    action.modal(client, log).update(next_view, failure_event="incident_status_update_new_update_failed")


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


@dataclass(frozen=True)
class _ModalAction:
    """What a status-updates modal payload carries: the view, the user, its private metadata and the button value."""

    view: dict[str, Any]
    user_id: str
    metadata: dict[str, Any]
    target: dict[str, Any]

    @property
    def view_id(self) -> str:
        return str(self.view.get("id", ""))

    @property
    def channel_id(self) -> str:
        return str(self.metadata.get("channel_id", ""))

    @property
    def locale(self) -> str:
        return str(self.metadata.get("locale") or "en-US")

    @property
    def incident_id(self) -> str:
        return str(self.metadata.get("incident_id", ""))

    @property
    def sequence(self) -> int:
        """The review form's draft sequence, from the private metadata."""
        return int(self.metadata.get("sequence") or 0)

    def list_metadata(self, channel_id: str | None = None) -> str:
        """Private metadata for a list or error view: the channel and locale."""
        return json.dumps({"channel_id": self.channel_id if channel_id is None else channel_id, "locale": self.locale})

    def review_metadata(self, incident_id: str, sequence: Any) -> str:
        """Private metadata for a review form: the channel, locale, incident and draft sequence."""
        return json.dumps(
            {"channel_id": self.channel_id, "locale": self.locale, "incident_id": incident_id, "sequence": sequence}
        )

    def bind(self, name: str, channel_id: str | None = None) -> structlog.stdlib.BoundLogger:
        """A logger bound to the action name, user, channel and view."""
        channel = self.channel_id if channel_id is None else channel_id
        log: structlog.stdlib.BoundLogger = logger.bind(
            action=name, user_id=self.user_id, channel_id=channel, view_id=self.view_id
        )
        return log

    def modal(self, client: Any, log: structlog.stdlib.BoundLogger, *, hashed: bool = True) -> _ModalCursor:
        """A cursor on the modal; ``hashed=False`` after an ack that already changed the view."""
        return _ModalCursor(client, self.view_id, self.view.get("hash") if hashed else None, log)


def _parse_action(body: dict[str, Any]) -> _ModalAction:
    """Read a block-actions or view-submission payload into a ``_ModalAction``."""
    view = body.get("view") or {}
    return _ModalAction(
        view=view,
        user_id=str((body.get("user") or {}).get("id", "")),
        metadata=_parse_metadata(view.get("private_metadata")),
        target=_parse_metadata(((body.get("actions") or [{}])[0]).get("value")),
    )


class _ProfileLabelArgs(TypedDict):
    labels_en: ProfileLabels
    labels_fr: ProfileLabels


def _profile_labels() -> _ProfileLabelArgs:
    """The English and French labels the copy-ready text is rendered with, as keyword arguments."""
    return {"labels_en": build_profile_labels("en-US"), "labels_fr": build_profile_labels("fr-FR")}


def handle_review_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of the Review button: replace the modal in place with the review form.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; the button value names the incident and sequence.
        client: Bolt Slack web client.
    """
    ack()
    action = _parse_action(body)
    log = action.bind("incident_status_update_review")
    incident_id, sequence = str(action.target.get("incident_id", "")), action.target.get("sequence")

    result = asyncio.run(open_status_update_form(incident_id, sequence)) if isinstance(sequence, int) else None
    if result is not None and result.is_success and result.data is not None:
        metadata = action.review_metadata(incident_id, sequence)
        next_view = build_review_view(result.data.update, action.locale, metadata, with_ai=result.data.ai_available)
    else:
        error_code = result.error_code if result is not None else None
        log.warning("incident_status_update_review_failed", error_code=error_code)
        next_view = build_review_error_view(error_code, action.locale, action.list_metadata())
    action.modal(client, log).update(next_view, failure_event="incident_status_update_review_update_failed")


def handle_open_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of Open on an approved update: replace the modal in place with its copy-ready text.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; the button value names the incident and sequence.
        client: Bolt Slack web client.
    """
    ack()
    action = _parse_action(body)
    log = action.bind("incident_status_update_open")
    incident_id, sequence = str(action.target.get("incident_id", "")), action.target.get("sequence")

    result = None
    if isinstance(sequence, int):
        result = asyncio.run(read_published(incident_id, sequence, **_profile_labels()))
    if result is not None and result.is_success and result.data is not None:
        next_view = build_copy_ready_view(result.data.text, action.locale, action.list_metadata(), update=result.data.update)
    else:
        error_code = result.error_code if result is not None else None
        log.warning("incident_status_update_open_failed", error_code=error_code)
        next_view = build_draft_error_view(error_code, action.locale, action.list_metadata())
    action.modal(client, log).update(next_view, failure_event="incident_status_update_open_update_failed")


def handle_history_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of Back: replace the modal in place with the incident's status-updates list.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; the button value names the channel.
        client: Bolt Slack web client.
    """
    ack()
    action = _parse_action(body)
    channel_id = str(action.target.get("channel_id", ""))
    log = action.bind("incident_status_update_history", channel_id=channel_id)
    metadata = action.list_metadata(channel_id)

    result = get_status_update_overview(channel_id)
    if result.is_success and result.data is not None:
        next_view = build_overview_view(result.data, action.locale, metadata)
    else:
        log.warning("incident_status_update_history_failed", status=result.status, error_code=result.error_code)
        next_view = build_draft_error_view(result.error_code, action.locale, metadata)
    action.modal(client, log).update(next_view, failure_event="incident_status_update_history_update_failed")


def handle_published_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of the published toggle: set the target state, then show the record's copy-ready text.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; the button value names the incident, sequence and target state.
        client: Bolt Slack web client.
    """
    ack()
    action = _parse_action(body)
    log = action.bind("incident_status_update_published")
    incident_id, sequence = str(action.target.get("incident_id", "")), action.target.get("sequence")
    published = action.target.get("published")

    result = None
    if isinstance(sequence, int) and isinstance(published, bool):
        result = asyncio.run(
            set_published_and_render(incident_id, sequence, published=published, actor=action.user_id, **_profile_labels())
        )
    if result is not None and result.is_success and result.data is not None:
        next_view = build_copy_ready_view(result.data.text, action.locale, action.list_metadata(), update=result.data.update)
    else:
        error_code = result.error_code if result is not None else None
        log.warning("incident_status_update_published_failed", error_code=error_code)
        next_view = build_published_error_view(error_code, action.locale, action.list_metadata())
    action.modal(client, log).update(next_view, failure_event="incident_status_update_published_update_failed")


def handle_generate_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of Draft with AI in the review form: fill the draft from the typed values, then update the modal in place.

    A fill or a carry forward shows the new draft's form with a notice. A
    refusal or failure keeps the previous draft and re-renders the form from the
    responder's values with their instructions (and the confirmation checkbox
    after a security refusal); a conflict shows the review conflict view.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; carries the view id, hash, review metadata and form state.
        client: Bolt Slack web client.
    """
    ack()
    action = _parse_action(body)
    log = action.bind("incident_status_update_generate")
    modal = action.modal(client, log)
    instructions, security_confirmed = parse_ai_form(action.view)
    current_metadata = action.review_metadata(action.incident_id, action.sequence)

    def show_generating() -> None:
        modal.update(
            build_generating_view(action.locale, current_metadata),
            failure_event="incident_status_update_generating_update_failed",
        )

    result = asyncio.run(
        fill_status_update_form(
            action.channel_id,
            action.incident_id,
            action.sequence,
            edit=parse_review_submission(action.view),
            author=action.user_id,
            wording=build_no_new_information_wording(),
            instructions=instructions,
            security_confirmed=security_confirmed,
            on_started=show_generating,
        )
    )
    if result.is_success and result.data is not None:
        if result.data.kept:
            log.warning("incident_status_update_generate_failed", error_code=result.data.failure_code)
        metadata = action.review_metadata(action.incident_id, result.data.update.sequence)
        next_view = build_filled_form_view(result.data, action.locale, metadata, instructions=instructions)
    else:
        log.warning("incident_status_update_generate_failed", error_code=result.error_code)
        next_view = build_review_error_view(result.error_code, action.locale, current_metadata)
    modal.update(next_view, failure_event="incident_status_update_generate_update_failed")


def handle_save_action(ack: Callable[[], Any], body: dict[str, Any], client: Any) -> None:
    """Handle a press of Save draft in the review form: store the typed values, then update the modal in place.

    A save shows the saved draft's form with a notice. A stale sequence shows
    the review conflict view. Any other failure, or a form with no readable
    stage, re-renders the typed values over the stored draft with a notice.

    Args:
        ack: Bolt ack callable, called first.
        body: Block-actions payload; carries the view id, hash, review metadata and form state.
        client: Bolt Slack web client.
    """
    ack()
    action = _parse_action(body)
    log = action.bind("incident_status_update_save")
    edit = parse_review_submission(action.view)

    result = asyncio.run(
        save_status_update_form(action.channel_id, action.incident_id, action.sequence, edit=edit, author=action.user_id)
    )
    if result.is_success and result.data is not None:
        if result.data.kept:
            log.warning("incident_status_update_save_failed", error_code=result.data.failure_code)
        metadata = action.review_metadata(action.incident_id, result.data.update.sequence)
        next_view = build_saved_form_view(result.data, action.locale, metadata)
    else:
        log.warning("incident_status_update_save_failed", status=result.status, error_code=result.error_code)
        metadata = action.review_metadata(action.incident_id, action.sequence)
        next_view = build_review_error_view(result.error_code, action.locale, metadata)
    action.modal(client, log).update(next_view, failure_event="incident_status_update_save_update_failed")


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
    action = _parse_action(body)
    metadata = action.review_metadata(action.incident_id, action.metadata.get("sequence"))
    edit = parse_review_submission(action.view)
    blank = ("stage",) if edit is None else edit.blank_fields()
    if edit is None or blank:
        ack(response_action="errors", errors=build_review_field_errors(blank, action.locale))
        return
    ack(response_action="update", view=build_saving_view(action.locale, metadata))

    log = action.bind("incident_status_update_approval")
    result = asyncio.run(
        approve_and_publish(action.incident_id, action.sequence, approver=action.user_id, edit=edit, **_profile_labels())
    )
    if result.is_success and result.data is not None:
        next_view = build_copy_ready_view(result.data, action.locale, metadata)
    else:
        log.warning("incident_status_update_approval_failed", status=result.status, error_code=result.error_code)
        next_view = build_review_error_view(result.error_code, action.locale, metadata)
    action.modal(client, log, hashed=False).update(next_view, failure_event="incident_status_update_approval_update_failed")


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
