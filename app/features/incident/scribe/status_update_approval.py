"""Review and approve an incident's pending status update.

Platform-neutral use case behind the status-updates modal. The approver submits
the stage and both languages' fields; approval moves the draft to ``APPROVED``
with the approver and time and stops there: nothing is published.
``approve_and_publish`` approves, then renders the approved record through the
``StatusPagePublisher`` as copy-ready text, in one call.

The functions are async like ``generate_status_update_draft`` and call the synchronous
core store inline. This module imports only ``core.api`` from the core.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import structlog

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateStore,
    get_status_update_store,
)
from features.incident.scribe import providers
from features.incident.scribe.comms_profile import ProfileLabels
from features.incident.scribe.domain import CopyReadyText, StatusUpdateEdit
from features.incident.scribe.ports import StatusPagePublisher
from features.incident.scribe.settings import get_incident_status_update_settings
from features.incident.scribe.status_update import next_update_at_for

logger = structlog.get_logger()

_STAGE_ORDER = tuple(StatusUpdateStage)


async def get_draft_for_review(
    incident_id: str,
    sequence: int,
    *,
    store: StatusUpdateStore | None = None,
) -> OperationResult[StatusUpdate]:
    """Return the incident's latest record when it is a draft at ``sequence``.

    Returns:
        Success with the draft. ``STATUS_UPDATE_CONFLICT`` when a newer record
        exists or the target is not a draft; otherwise the store's classified error.
    """
    store = store or get_status_update_store()
    listed = store.list_for_incident(incident_id)
    if not listed.is_success or listed.data is None:
        return _failure(listed)
    latest = listed.data[0] if listed.data else None
    if latest is None or latest.sequence != sequence or latest.state is not StatusUpdateState.DRAFT:
        return _conflict("The status update is no longer the pending draft")
    return OperationResult.success(data=latest)


async def approve_status_update(
    incident_id: str,
    sequence: int,
    *,
    approver: str,
    edit: StatusUpdateEdit,
    store: StatusUpdateStore | None = None,
    now: datetime | None = None,
) -> OperationResult[StatusUpdate]:
    """Approve the pending draft at ``sequence`` with the approver's edits.

    Args:
        incident_id: The incident the update belongs to.
        sequence: The draft the approver reviewed.
        approver: Platform user id of the approver.
        edit: The reviewed stage and fields in both languages.
        store: Holds the incident's status updates; core's by default.
        now: The current time; injected in tests.

    Returns:
        Success with the ``APPROVED`` record, also when the same approver
        repeats an identical approval. ``STATUS_UPDATE_FIELDS_INVALID`` naming
        blank fields (before any store call), ``STATUS_UPDATE_CONFLICT`` for a
        stale sequence, a non-draft target or a different concurrent approval,
        ``STATUS_UPDATE_STAGE_BELOW_FLOOR`` for a stage below the latest
        approved one, or the store's classified error.
    """
    log = logger.bind(operation="approve_status_update", incident_id=incident_id, sequence=sequence, approver=approver)
    blank = edit.blank_fields()
    if blank:
        log.info("incident_status_update_fields_invalid", fields=blank)
        return OperationResult.permanent_error(
            message=f"These status update fields are blank: {', '.join(blank)}",
            error_code=ErrorCode.STATUS_UPDATE_FIELDS_INVALID,
        )

    store = store or get_status_update_store()
    listed = store.list_for_incident(incident_id)
    if not listed.is_success or listed.data is None:
        return _failure(listed)
    records = listed.data
    if not records or records[0].sequence != sequence:
        log.warning("incident_status_update_stale_sequence")
        return _conflict("The status update has a newer record than the one reviewed")
    target = records[0]
    if target.state is not StatusUpdateState.DRAFT:
        if _is_same_approval(target, approver, edit):
            log.info("incident_status_update_approval_replayed")
            return OperationResult.success(data=target)
        log.warning("incident_status_update_not_a_draft", state=target.state)
        return _conflict("The status update is no longer a draft")

    last_public = next((record for record in records if record.state is not StatusUpdateState.DRAFT), None)
    if last_public is not None and _STAGE_ORDER.index(edit.stage) < _STAGE_ORDER.index(last_public.stage):
        log.info("incident_status_update_stage_below_floor", stage=edit.stage, floor=last_public.stage)
        return OperationResult.permanent_error(
            message="The stage cannot be earlier than the latest approved update's stage",
            error_code=ErrorCode.STATUS_UPDATE_STAGE_BELOW_FLOOR,
        )

    now = now or datetime.now(UTC)
    next_update_at = target.next_update_at
    if edit.stage is not target.stage:
        next_update_at = next_update_at_for(edit.stage, get_incident_status_update_settings(), now)
    approved = replace(
        target,
        state=StatusUpdateState.APPROVED,
        stage=edit.stage,
        en=edit.en,
        fr=edit.fr,
        next_update_at=next_update_at,
        approver=approver,
        approved_at=now,
    )
    moved = store.transition(approved, expected_state=StatusUpdateState.DRAFT)
    if moved.is_success:
        log.info("incident_status_update_approved")
        return OperationResult.success(data=approved)
    if moved.error_code != ErrorCode.STATUS_UPDATE_CONFLICT:
        return _failure(moved)

    # One re-read, no retry loop: an identical winning approval is a success, anything else a conflict.
    winner = store.latest(incident_id).data
    if winner is not None and winner.sequence == sequence and _is_same_approval(winner, approver, edit):
        log.info("incident_status_update_approval_replayed")
        return OperationResult.success(data=winner)
    log.warning("incident_status_update_conflict")
    return _conflict("Another approval of this status update was stored first")


async def approve_and_publish(
    incident_id: str,
    sequence: int,
    *,
    approver: str,
    edit: StatusUpdateEdit,
    labels_en: ProfileLabels,
    labels_fr: ProfileLabels,
    publisher: StatusPagePublisher | None = None,
) -> OperationResult[CopyReadyText]:
    """Approve the pending draft at ``sequence``, then render the approved record as copy-ready text.

    Args:
        incident_id: The incident the update belongs to.
        sequence: The draft the approver reviewed.
        approver: Platform user id of the approver.
        edit: The reviewed stage and fields in both languages.
        labels_en: English labels and zone suffix for the rendering.
        labels_fr: French labels and zone suffix for the rendering.
        publisher: Renders the approved record; the scribe's by default.

    Returns:
        Success with the copy-ready text. A refused approval is returned with
        its classified error and nothing is rendered; a rendering failure is
        returned as the publisher classified it.
    """
    approved = await approve_status_update(incident_id, sequence, approver=approver, edit=edit)
    if not approved.is_success or approved.data is None:
        return _failure(approved)
    publisher = publisher or providers.get_status_page_publisher()
    return await publisher.publish(approved.data, labels_en=labels_en, labels_fr=labels_fr)


def _is_same_approval(record: StatusUpdate, approver: str, edit: StatusUpdateEdit) -> bool:
    """Whether ``record`` is the approved record this approver and edit would produce."""
    return (
        record.state is StatusUpdateState.APPROVED
        and record.approver == approver
        and record.stage is edit.stage
        and record.en == edit.en
        and record.fr == edit.fr
    )


def _conflict(message: str) -> OperationResult[StatusUpdate]:
    return OperationResult.permanent_error(message=message, error_code=ErrorCode.STATUS_UPDATE_CONFLICT)


def _failure[T](result: OperationResult[Any]) -> OperationResult[T]:
    """Carry an error result's classification over to another payload type."""
    return OperationResult.error(
        result.status,
        message=result.message or "status update failed",
        error_code=result.error_code,
        retry_after=result.retry_after,
    )
