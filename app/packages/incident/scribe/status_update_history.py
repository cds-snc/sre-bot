"""Read one approved status update of an incident by its sequence.

Platform-neutral read behind the status-updates modal's Open button. The
function is async like the other status-update use cases and calls the
synchronous core store inline. It writes nothing. This module imports only
``core.api`` from the core.
"""

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from packages.incident.core.api import StatusUpdate, StatusUpdateState, StatusUpdateStore, get_status_update_store


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
    store = store or get_status_update_store()
    listed = store.list_for_incident(incident_id)
    if not listed.is_success or listed.data is None:
        return OperationResult.error(
            listed.status,
            message=listed.message or "status update failed",
            error_code=listed.error_code,
            retry_after=listed.retry_after,
        )
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
