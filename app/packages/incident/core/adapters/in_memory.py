"""In-memory ``StatusUpdateStore`` with the DynamoDB adapter's observable rules.

For tests and local runs: appends only where nothing is stored, an identical
replay is success, state changes only from the expected state, newest first.
"""

from collections.abc import Sequence

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from packages.incident.core.domain import StatusUpdate, StatusUpdateState


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
