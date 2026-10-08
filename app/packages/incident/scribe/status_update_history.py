"""Read one approved status update of an incident and mark it published or not.

Platform-neutral use cases behind the status-updates modal's Open button and the
copy-ready view's published toggle. The functions are async like the other
status-update use cases and call the synchronous core store inline. Reading
writes nothing; the toggle's only write is one store transition. Nothing is
posted anywhere. This module imports only ``core.api`` from the core.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import structlog

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from packages.incident.core.api import StatusUpdate, StatusUpdateState, StatusUpdateStore, get_status_update_store

logger = structlog.get_logger()


async def get_approved_update(
    incident_id: str,
    sequence: int,
    *,
    store: StatusUpdateStore | None = None,
) -> OperationResult[StatusUpdate]:
    """Return the incident's record at ``sequence`` when it is approved or published.

    Returns:
        Success with the record. ``STATUS_UPDATE_NOT_APPROVED`` when the record
        is a draft; ``STATUS_UPDATE_CONFLICT`` when the incident has no such
        sequence; otherwise the store's classified error.
    """
    return _read_approved(store or get_status_update_store(), incident_id, sequence)


async def set_published(
    incident_id: str,
    sequence: int,
    *,
    published: bool,
    actor: str,
    now: datetime | None = None,
    store: StatusUpdateStore | None = None,
) -> OperationResult[StatusUpdate]:
    """Mark the approved update at ``sequence`` as published, or as not published.

    Args:
        incident_id: The incident the update belongs to.
        sequence: The update the person toggled.
        published: The target state the button carried.
        actor: Platform user id of the person who toggled it.
        now: The current time; injected in tests.
        store: Holds the incident's status updates; core's by default.

    Returns:
        Success with the stored record, also when it already is in the target
        state (no write) or a concurrent writer put it there first.
        ``STATUS_UPDATE_NOT_APPROVED`` for a draft; ``STATUS_UPDATE_CONFLICT``
        for a missing sequence or a lost write whose record is not in the target
        state; otherwise the store's classified error.
    """
    log = logger.bind(operation="set_published", incident_id=incident_id, sequence=sequence, actor=actor, published=published)
    store = store or get_status_update_store()
    target_state = StatusUpdateState.PUBLISHED if published else StatusUpdateState.APPROVED
    read = _read_approved(store, incident_id, sequence)
    if not read.is_success or read.data is None:
        log.info("incident_status_update_published_refused", error_code=read.error_code)
        return read
    current = read.data
    if current.state is target_state:
        log.info("incident_status_update_published_unchanged")
        return read

    if published:
        changed = replace(current, state=target_state, published_at=now or datetime.now(UTC), published_by=actor)
    else:
        changed = replace(current, state=target_state, published_at=None, published_by=None)
    moved = store.transition(changed, expected_state=current.state)
    if moved.is_success:
        log.info("incident_status_update_published_set")
        return OperationResult.success(data=changed)
    if moved.error_code != ErrorCode.STATUS_UPDATE_CONFLICT:
        return _failure(moved)

    # One re-read, no retry loop: a concurrent writer that reached the target state is a success.
    reread = _read_approved(store, incident_id, sequence)
    if reread.is_success and reread.data is not None and reread.data.state is target_state:
        log.info("incident_status_update_published_replayed")
        return reread
    log.warning("incident_status_update_published_conflict")
    return OperationResult.permanent_error(
        message="The status update was changed by another writer", error_code=ErrorCode.STATUS_UPDATE_CONFLICT
    )


def _read_approved(store: StatusUpdateStore, incident_id: str, sequence: int) -> OperationResult[StatusUpdate]:
    """Return the record at ``sequence`` when it is approved or published, read from the incident's list."""
    listed = store.list_for_incident(incident_id)
    if not listed.is_success or listed.data is None:
        return _failure(listed)
    record = next((update for update in listed.data if update.sequence == sequence), None)
    if record is None:
        return OperationResult.permanent_error(
            message="The status update no longer exists", error_code=ErrorCode.STATUS_UPDATE_CONFLICT
        )
    if record.state is StatusUpdateState.DRAFT:
        return OperationResult.permanent_error(
            message="The status update is not approved", error_code=ErrorCode.STATUS_UPDATE_NOT_APPROVED
        )
    return OperationResult.success(data=record)


def _failure(result: OperationResult[Any]) -> OperationResult[StatusUpdate]:
    """Carry a store error's classification over to a status update payload type."""
    return OperationResult.error(
        result.status,
        message=result.message or "status update failed",
        error_code=result.error_code,
        retry_after=result.retry_after,
    )
