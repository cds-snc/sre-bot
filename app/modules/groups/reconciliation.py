from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from core.logging import get_module_logger

logger = get_module_logger()


@dataclass
class FailedPropagation:
    """Represents a failed propagation/reconciliation item that needs retry.

    Fields:
    - id: unique identifier for the reconciliation record (string or int as stored by DB)
    - group_id: canonical NormalizedGroup.id this failure relates to
    - provider: provider name that attempted the propagation
    - payload_raw: original provider payload (string or dict) - store minimal redacted form
    - op_status: OperationResult.status string (e.g. "permanent_error", "retryable_error")
    - op_data: Optional metadata from OperationResult.data (dict)
    - attempts: number of delivery attempts
    - last_error: last error message seen
    - created_at / updated_at: timestamps for lifecycle tracking
    """

    id: Optional[str] = None
    group_id: str | None = None
    provider: str | None = None
    payload_raw: Optional[Dict[str, Any]] = None
    op_status: Optional[str] = None
    op_data: Optional[Dict[str, Any]] = None
    attempts: int = 0
    last_error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class ReconciliationStore(Protocol):
    """Storage adapter interface for failed-propagation records.

    Implementations must provide atomic claim semantics for workers (claim -> process -> mark).
    This protocol is intentionally minimal; concrete implementations may use Postgres, DynamoDB,
    or another durable store. See REQUIRED_CHANGES.md PHASE 9 for recommended semantics.
    """

    def save_failed_propagation(self, record: FailedPropagation) -> str:
        """Persist a new failed propagation record and return its id."""

    def fetch_due(self, limit: int = 100) -> List[FailedPropagation]:
        """Return up to `limit` records that are due for retry.

        This should only return records that are not currently claimed by a worker or whose
        claim lease has expired.
        """

    def claim_record(self, record_id: str, worker_id: str, lease_seconds: int) -> bool:
        """Attempt to claim a record for processing. Return True if claim succeeded."""

    def mark_success(self, record_id: str) -> None:
        """Mark a claimed record as successfully reconciled and remove it from the queue."""

    def mark_permanent_failure(self, record_id: str, reason: str) -> None:
        """Mark a record as permanently failed (move to dead-letter or flag)."""

    def increment_attempt(
        self, record_id: str, last_error: Optional[str] = None
    ) -> None:
        """Increment attempt counter and update last_error/updated_at."""


# Small in-memory helper (NOT for production) to ease local development and tests.
class InMemoryReconciliationStore:
    def __init__(self) -> None:
        self._store: Dict[str, FailedPropagation] = {}
        self._claims: Dict[str, Dict[str, Any]] = {}
        self._next_id = 1

    def save_failed_propagation(self, record: FailedPropagation) -> str:
        record_id = str(self._next_id)
        self._next_id += 1
        record.id = record_id
        self._store[record_id] = record
        logger.debug("saved failed propagation", record_id=record_id)
        return record_id

    def fetch_due(self, limit: int = 100) -> List[FailedPropagation]:
        # Return records that are not claimed
        due = [r for rid, r in self._store.items() if rid not in self._claims]
        return due[:limit]

    def claim_record(self, record_id: str, worker_id: str, lease_seconds: int) -> bool:
        if record_id not in self._store:
            return False
        if record_id in self._claims:
            return False
        self._claims[record_id] = {
            "worker": worker_id,
            "expires_at": datetime.utcnow().timestamp() + lease_seconds,
        }
        logger.debug("claimed record", record_id=record_id, worker=worker_id)
        return True

    def mark_success(self, record_id: str) -> None:
        if record_id in self._store:
            del self._store[record_id]
        if record_id in self._claims:
            del self._claims[record_id]
        logger.debug("marked success", record_id=record_id)

    def mark_permanent_failure(self, record_id: str, reason: str) -> None:
        rec = self._store.get(record_id)
        if not rec:
            return
        rec.op_status = "permanent_error"
        rec.last_error = reason
        logger.debug("marked permanent failure", record_id=record_id, reason=reason)

    def increment_attempt(
        self, record_id: str, last_error: Optional[str] = None
    ) -> None:
        rec = self._store.get(record_id)
        if not rec:
            return
        rec.attempts += 1
        rec.last_error = last_error
        rec.updated_at = datetime.utcnow()
        if record_id in self._claims:
            del self._claims[record_id]
        logger.debug("incremented attempt", record_id=record_id, attempts=rec.attempts)
