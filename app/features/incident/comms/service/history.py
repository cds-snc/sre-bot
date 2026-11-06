"""Read an incident's status updates: the pending draft and the approved history.

Platform-neutral read of the status-update command
(decisions/incident-management.md, External status updates). It resolves the
incident through the core's command check and drafts nothing.
"""

from contracts.operations import OperationResult
from features.incident.comms.domain import StatusUpdateOverview
from features.incident.comms.service._results import failure
from features.incident.core.api import (
    ConversationReference,
    IncidentStore,
    StatusUpdateState,
    StatusUpdateStore,
    find_incident_for_conversation,
)


def get_status_update_overview(
    incidents: IncidentStore,
    conversation: ConversationReference,
    *,
    store: StatusUpdateStore,
) -> OperationResult[StatusUpdateOverview]:
    """Return the incident's pending draft and approved updates, without drafting anything.

    Args:
        incidents: Reads the incident records.
        conversation: The incident conversation the command ran in.
        store: Holds the incident's status updates.

    Returns:
        Success with the latest record as ``pending`` when it is a draft, and
        every approved or published record newest first. Otherwise the command
        check's refusal (``NOT_AN_INCIDENT``, ``AMBIGUOUS_INCIDENT_CONVERSATION``) or
        the store's classified error.
    """
    incident = find_incident_for_conversation(incidents, conversation)
    if not incident.is_success or incident.data is None:
        return failure(incident)

    listed = store.list_for_incident(incident.data.id)
    if not listed.is_success or listed.data is None:
        return failure(listed)
    latest = listed.data[0] if listed.data else None
    pending = latest if latest is not None and latest.state is StatusUpdateState.DRAFT else None
    approved = tuple(update for update in listed.data if update.state is not StatusUpdateState.DRAFT)
    return OperationResult.success(data=StatusUpdateOverview(pending=pending, approved=approved))
