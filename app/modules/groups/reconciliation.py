import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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


class InMemoryReconciliationStore:
    """In-memory implementation with retry logic and exponential backoff.

    Thread-safe store for failed propagations with support for:
    - Exponential backoff (60s base, max 1 hour)
    - Max retry attempts (5 by default)
    - Dead letter queue for permanent failures
    - Claim-based processing (prevents duplicate work)
    """

    def __init__(self) -> None:
        self._store: Dict[str, FailedPropagation] = {}
        self._claims: Dict[str, Dict[str, Any]] = {}
        self._dlq: Dict[str, FailedPropagation] = {}
        self._lock = threading.Lock()
        self._next_id = 1

        # Configuration
        self._max_attempts = 5
        self._base_retry_delay_seconds = 60  # 1 minute
        self._max_retry_delay_seconds = 3600  # 1 hour

    def save_failed_propagation(self, record: FailedPropagation) -> str:
        """Save a new failed propagation record."""
        with self._lock:
            record_id = str(self._next_id)
            self._next_id += 1
            record.id = record_id
            record.attempts = 0
            record.created_at = datetime.utcnow()
            record.updated_at = datetime.utcnow()
            self._store[record_id] = record
            logger.info(
                "saved_failed_propagation",
                record_id=record_id,
                provider=record.provider,
                group_id=record.group_id,
            )
            return record_id

    def fetch_due(self, limit: int = 100) -> List[FailedPropagation]:
        """Return records that are due for retry (not claimed, within retry window)."""
        with self._lock:
            now = datetime.utcnow()
            due = []

            for record_id, record in self._store.items():
                # Skip if already claimed
                if record_id in self._claims:
                    claim = self._claims[record_id]
                    # Check if claim expired
                    if claim["expires_at"] > now.timestamp():
                        continue
                    else:
                        # Claim expired, remove it
                        del self._claims[record_id]

                # Calculate next retry time with exponential backoff
                retry_delay = self._calculate_retry_delay(record.attempts)
                next_retry_time = record.updated_at + timedelta(seconds=retry_delay)

                # Include if due for retry
                if now >= next_retry_time:
                    due.append(record)

                if len(due) >= limit:
                    break

            logger.debug(
                "fetched_due_records",
                count=len(due),
                total_store_size=len(self._store),
            )
            return due

    def _calculate_retry_delay(self, attempts: int) -> int:
        """Calculate exponential backoff delay in seconds."""
        delay = self._base_retry_delay_seconds * (2**attempts)
        return min(delay, self._max_retry_delay_seconds)

    def claim_record(self, record_id: str, worker_id: str, lease_seconds: int) -> bool:
        """Claim a record for processing."""
        with self._lock:
            if record_id not in self._store:
                return False
            if record_id in self._claims:
                # Check if existing claim expired
                claim = self._claims[record_id]
                if claim["expires_at"] > datetime.utcnow().timestamp():
                    return False  # Still claimed

            self._claims[record_id] = {
                "worker": worker_id,
                "expires_at": datetime.utcnow().timestamp() + lease_seconds,
            }
            logger.debug("claimed_record", record_id=record_id, worker=worker_id)
            return True

    def mark_success(self, record_id: str) -> None:
        """Remove successfully reconciled record from queue."""
        with self._lock:
            if record_id in self._store:
                record = self._store[record_id]
                logger.info(
                    "reconciliation_success",
                    record_id=record_id,
                    provider=record.provider,
                    attempts=record.attempts,
                )
                del self._store[record_id]
            if record_id in self._claims:
                del self._claims[record_id]

    def mark_permanent_failure(self, record_id: str, reason: str) -> None:
        """Move record to dead letter queue."""
        with self._lock:
            self._mark_permanent_failure_locked(record_id, reason)

    def _mark_permanent_failure_locked(self, record_id: str, reason: str) -> None:
        """Internal version of mark_permanent_failure (assumes lock is held)."""
        rec = self._store.get(record_id)
        if not rec:
            return

        rec.op_status = "permanent_error"
        rec.last_error = reason
        rec.updated_at = datetime.utcnow()

        # Move to DLQ
        self._dlq[record_id] = rec
        del self._store[record_id]

        if record_id in self._claims:
            del self._claims[record_id]

        logger.warning(
            "reconciliation_permanent_failure",
            record_id=record_id,
            provider=rec.provider,
            attempts=rec.attempts,
            reason=reason,
        )

    def increment_attempt(
        self, record_id: str, last_error: Optional[str] = None
    ) -> None:
        """Increment attempt counter and check for max retries."""
        with self._lock:
            rec = self._store.get(record_id)
            if not rec:
                return

            rec.attempts += 1
            rec.last_error = last_error
            rec.updated_at = datetime.utcnow()

            # Check if max attempts reached
            if rec.attempts >= self._max_attempts:
                self._mark_permanent_failure_locked(
                    record_id,
                    f"Max retries ({self._max_attempts}) exceeded: {last_error}",
                )
            else:
                # Release claim so it can be retried later
                if record_id in self._claims:
                    del self._claims[record_id]

                logger.info(
                    "reconciliation_retry_scheduled",
                    record_id=record_id,
                    attempts=rec.attempts,
                    max_attempts=self._max_attempts,
                    next_retry_in_seconds=self._calculate_retry_delay(rec.attempts),
                )

    def get_dlq_entries(self) -> List[FailedPropagation]:
        """Get all dead letter queue entries (for monitoring)."""
        with self._lock:
            return list(self._dlq.values())

    def get_stats(self) -> dict:
        """Get reconciliation queue statistics."""
        with self._lock:
            return {
                "active_records": len(self._store),
                "claimed_records": len(self._claims),
                "dlq_records": len(self._dlq),
            }
