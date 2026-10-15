"""In-memory incident core stores with the real stores' observable rules.

For tests and local runs. ``InMemoryStatusUpdateStore``: appends only where
nothing is stored, an identical replay is success, state changes only from the
expected state, newest first. ``InMemoryIncidentStore``: the incident reads
with the same classifications as ``RecordIncidentStore``.
"""

from collections.abc import Sequence

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from features.incident.core.domain import ConversationReference, Incident, StatusUpdate, StatusUpdateState
from features.incident.core.store import IncidentStore, ambiguous_conversation, no_such_incident, not_an_incident


class InMemoryStatusUpdateStore:
    """Hold status updates in a dict keyed by incident id and sequence."""

    def __init__(self) -> None:
        self._updates: dict[tuple[str, int], StatusUpdate] = {}

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        """Store a new update at its sequence; a different record already there is a conflict."""
        stored = self._updates.get((update.incident_id, update.sequence))
        if stored is not None and stored != update:
            return _conflict()
        self._updates[(update.incident_id, update.sequence)] = update
        return OperationResult.success(data=update)

    def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        """Replace the stored update with ``update`` while its stored state is ``expected_state``.

        Raises:
            ValueError: ``expected_state`` cannot move to ``update.state``.
        """
        if not expected_state.can_move_to(update.state):
            raise ValueError(f"no status update transition from {expected_state} to {update.state}")
        stored = self._updates.get((update.incident_id, update.sequence))
        if stored == update:
            return OperationResult.success(data=update)
        if stored is None or stored.state is not expected_state:
            return _conflict()
        self._updates[(update.incident_id, update.sequence)] = update
        return OperationResult.success(data=update)

    def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        """Return the incident's highest-sequence update, or success with ``None`` when it has none."""
        updates = self._newest_first(incident_id)
        return OperationResult.success(data=updates[0] if updates else None)

    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        """Return every update of the incident, newest first."""
        return OperationResult.success(data=self._newest_first(incident_id))

    def _newest_first(self, incident_id: str) -> tuple[StatusUpdate, ...]:
        updates = (update for (owner, _), update in self._updates.items() if owner == incident_id)
        return tuple(sorted(updates, key=lambda update: update.sequence, reverse=True))


def _conflict[T]() -> OperationResult[T]:
    return OperationResult.error(
        OperationStatus.PERMANENT_ERROR,
        message="The status update was changed or taken by another writer.",
        error_code=ErrorCode.STATUS_UPDATE_CONFLICT,
    )


class InMemoryIncidentStore(IncidentStore):
    """Hold seeded incidents in a dict keyed by id; every seeded incident is readable.

    Open incidents are listed by ``declared_at``, a stand-in for the
    ``opened_at`` time the real store orders by and this fake does not hold.
    """

    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        self._open: set[str] = set()

    def seed(self, incident: Incident, *, open: bool | None = None) -> None:
        """Store ``incident``; ``open`` puts it in the open list and defaults to whether its status is open."""
        self._incidents[incident.id] = incident
        if incident.status.is_open if open is None else open:
            self._open.add(incident.id)
        else:
            self._open.discard(incident.id)

    def get(self, incident_id: str) -> OperationResult[Incident]:
        """Return the seeded incident with this id."""
        incident = self._incidents.get(incident_id)
        return OperationResult.success(data=incident) if incident is not None else no_such_incident()

    def find_by_conversation(self, conversation: ConversationReference) -> OperationResult[Incident]:
        """Return the one seeded incident with the same conversation system, tenant and id."""
        matches = [
            incident
            for incident in self._incidents.values()
            if incident.conversation is not None
            and (incident.conversation.system, incident.conversation.tenant, incident.conversation.vendor_id)
            == (conversation.system, conversation.tenant, conversation.vendor_id)
        ]
        if not conversation.vendor_id.strip() or not matches:
            return not_an_incident()
        if len(matches) > 1:
            return ambiguous_conversation(conversation, match_count=len(matches))
        return OperationResult.success(data=matches[0])

    def list_open(self) -> OperationResult[Sequence[Incident]]:
        """Return the incidents seeded open, oldest declaration first."""
        incidents = (self._incidents[incident_id] for incident_id in self._open)
        return OperationResult.success(data=sorted(incidents, key=lambda incident: incident.declared_at))

    def read_security_flag(self, incident_id: str) -> OperationResult[bool]:
        """Return the seeded incident's security flag."""
        incident = self._incidents.get(incident_id)
        return OperationResult.success(data=incident.security_incident) if incident is not None else no_such_incident()
