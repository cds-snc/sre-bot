"""Slack block-action listeners for the incident scribe status-updates modal.

The Draft button is a native Bolt listener registered through the command
registrar. It acks, makes one call to the status-update service and updates the
modal with the result or a localized error. The service calls back just before
a model call so the modal shows a drafting state only then. For a security or
unknown-flag incident the service refuses until the responder confirms, so the
modal shows a confirmation view whose Confirm and draft button calls the
service again with confirmation; Cancel is the view's close button. Slack API
failures are logged and never raised; nothing is posted to the channel.

The Review button replaces the modal in place with the review form. Submitting
it acks with field errors for blank fields, or with a saving view; the approval
and the copy-ready rendering then run in one event loop and the modal is updated
by view id to the copy-ready text or an error. Wording and views come from
``platforms.slack``, the only module that translates.

The reopened copy-ready view's toggle marks the update published or not
published (the button carries the target state), then re-renders the stored
record in place. It writes only the update's state; nothing is posted.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import structlog

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from contracts.slack.registrar import SlackCommandRegistrar
from packages.incident.core.api import StatusUpdate
from packages.incident.scribe import providers
from packages.incident.scribe.domain import CopyReadyText, StatusUpdateEdit
from packages.incident.scribe.platforms.slack import (
    CONFIRM_ACTION_ID,
    DRAFT_ACTION_ID,
    HISTORY_ACTION_ID,
    OPEN_ACTION_ID,
    PUBLISHED_ACTION_ID,
    REVIEW_ACTION_ID,
    REVIEW_CALLBACK_ID,
    build_copy_ready_view,
    build_draft_error_view,
    build_drafting_view,
    build_no_new_information_wording,
    build_overview_view,
    build_profile_labels,
    build_published_error_view,
    build_result_view,
    build_review_error_view,
    build_review_field_errors,
    build_review_view,
    build_saving_view,
    build_security_confirmation_view,
    parse_review_submission,
)
from packages.incident.scribe.status_update import draft_status_update, get_status_update_overview
from packages.incident.scribe.status_update_approval import (
    approve_status_update,
    get_draft_for_review,
    validate_approval_edit,
)
from packages.incident.scribe.status_update_history import get_approved_update, set_published

logger = structlog.get_logger()


def register(registrar: SlackCommandRegistrar) -> None:
    """Register the Draft, Confirm and draft, Review, Open, Back and published toggle listeners and the approval submission.

    Args:
        registrar: Slack command registrar.
    """
    registrar.register_block_action(DRAFT_ACTION_ID, handle_draft_action)
    registrar.register_block_action(CONFIRM_ACTION_ID, handle_draft_confirmed_action)
    registrar.register_block_action(REVIEW_ACTION_ID, handle_review_action)
    registrar.register_block_action(OPEN_ACTION_ID, handle_open_action)
    registrar.register_block_action(HISTORY_ACTION_ID, handle_history_action)
    registrar.register_block_action(PUBLISHED_ACTION_ID, handle_published_action)
    registrar.register_view_submission(REVIEW_CALLBACK_ID, handle_review_submission)


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


def _run_draft(body: dict[str, Any], client: Any, *, security_confirmed: bool) -> None:
    """Draft through the service and update the modal with the confirmation, result or error."""
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
        )
    )
    if result.is_success and result.data is not None:
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
