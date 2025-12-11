"""Generic retry record storage.

This module provides storage interfaces and implementations for retry records.
The protocol-based design allows for multiple storage backends (in-memory, DynamoDB, Redis, etc.).
"""

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Protocol

from infrastructure.observability import get_module_logger
from infrastructure.resilience.retry.config import RetryConfig
from infrastructure.resilience.retry.models import RetryRecord

logger = get_module_logger()


class RetryStore(Protocol):
    """Storage interface for retry records.

    Implementations must provide atomic claim semantics for workers to prevent
    duplicate processing. The protocol supports various storage backends while
    maintaining consistent behavior.

    Methods:
        save: Persist a new retry record and return its ID
        fetch_due: Return records that are due for retry (not claimed, within retry window)
        claim_record: Attempt to claim a record for processing
        mark_success: Remove successfully processed record from queue
        mark_permanent_failure: Move record to dead letter queue
        increment_attempt: Increment attempt counter and reschedule
    """

    def save(self, record: RetryRecord) -> str:
        """Persist a new retry record and return its ID.

        Args:
            record: RetryRecord to save

        Returns:
            Unique identifier for the saved record
        """
        ...

    def fetch_due(self, limit: int = 100) -> List[RetryRecord]:
        """Return records that are due for retry.

        Should only return records that are:
        - Not currently claimed by a worker
        - Have a next_retry_at time in the past
        - Have not exceeded max attempts

        Args:
            limit: Maximum number of records to return

        Returns:
            List of retry records due for processing
        """
        ...

    def claim_record(self, record_id: str, worker_id: str, lease_seconds: int) -> bool:
        """Attempt to claim a record for processing.

        Args:
            record_id: ID of record to claim
            worker_id: Identifier of the worker claiming the record
            lease_seconds: How long the claim should last

        Returns:
            True if claim succeeded, False if already claimed
        """
        ...

    def mark_success(self, record_id: str) -> None:
        """Mark record as successfully processed and remove from queue.

        Args:
            record_id: ID of record to mark as successful
        """
        ...

    def mark_permanent_failure(self, record_id: str, reason: str) -> None:
        """Mark record as permanently failed and move to DLQ.

        Args:
            record_id: ID of record to mark as failed
            reason: Reason for permanent failure
        """
        ...

    def increment_attempt(self, record_id: str, last_error: str | None = None) -> None:
        """Increment attempt counter and reschedule for retry.

        This should also release any claim on the record so it can be
        retried later. If max attempts are reached, should move to DLQ.

        Args:
            record_id: ID of record to increment
            last_error: Optional error message from the failed attempt
        """
        ...


class InMemoryRetryStore:
    """In-memory implementation of RetryStore with exponential backoff.

    Thread-safe store for retry records with support for:
    - Configurable exponential backoff
    - Configurable max retry attempts
    - Dead letter queue for permanent failures
    - Claim-based processing (prevents duplicate work)

    This implementation is suitable for single-instance deployments or development.
    For production multi-instance deployments, consider DynamoDB or Redis implementations.

    Attributes:
        config: RetryConfig controlling retry behavior
    """

    def __init__(self, config: RetryConfig | None = None) -> None:
        """Initialize the in-memory store.

        Args:
            config: Optional RetryConfig. If not provided, uses defaults.
        """
        self._store: Dict[str, RetryRecord] = {}
        self._claims: Dict[str, Dict[str, Any]] = {}
        self._dlq: Dict[str, RetryRecord] = {}
        self._lock = threading.Lock()
        self._next_id = 1

        # Configuration
        self.config = config or RetryConfig()

    def save(self, record: RetryRecord) -> str:
        """Save a new retry record."""
        with self._lock:
            record_id = str(self._next_id)
            self._next_id += 1
            record.id = record_id
            record.attempts = 0
            record.created_at = datetime.now(timezone.utc)
            record.updated_at = datetime.now(timezone.utc)
            # Set next_retry_at to now (immediate retry)
            record.next_retry_at = datetime.now(timezone.utc)
            self._store[record_id] = record

            logger.info(
                "retry_record_saved",
                record_id=record_id,
                operation_type=record.operation_type,
            )
            return record_id

    def fetch_due(self, limit: int = 100) -> List[RetryRecord]:
        """Return records that are due for retry (not claimed, within retry window)."""
        with self._lock:
            now = datetime.now(timezone.utc)
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
                        logger.debug(
                            "retry_claim_expired",
                            record_id=record_id,
                            worker=claim["worker"],
                        )

                # Check if due for retry
                if record.next_retry_at and record.next_retry_at <= now:
                    due.append(record)

                if len(due) >= limit:
                    break

            logger.debug(
                "fetched_due_retry_records",
                count=len(due),
                total_store_size=len(self._store),
            )
            return due

    def claim_record(self, record_id: str, worker_id: str, lease_seconds: int) -> bool:
        """Claim a record for processing."""
        with self._lock:
            if record_id not in self._store:
                logger.warning("retry_claim_failed_not_found", record_id=record_id)
                return False

            if record_id in self._claims:
                # Check if existing claim expired
                claim = self._claims[record_id]
                if claim["expires_at"] > datetime.now(timezone.utc).timestamp():
                    logger.debug(
                        "retry_claim_failed_already_claimed",
                        record_id=record_id,
                        current_worker=claim["worker"],
                    )
                    return False  # Still claimed

            self._claims[record_id] = {
                "worker": worker_id,
                "expires_at": datetime.now(timezone.utc).timestamp() + lease_seconds,
            }
            logger.debug(
                "retry_record_claimed",
                record_id=record_id,
                worker=worker_id,
            )
            return True

    def mark_success(self, record_id: str) -> None:
        """Remove successfully processed record from queue."""
        with self._lock:
            if record_id in self._store:
                record = self._store[record_id]
                logger.info(
                    "retry_success",
                    record_id=record_id,
                    operation_type=record.operation_type,
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

        rec.last_error = reason
        rec.updated_at = datetime.now(timezone.utc)

        # Move to DLQ
        self._dlq[record_id] = rec
        del self._store[record_id]

        if record_id in self._claims:
            del self._claims[record_id]

        logger.warning(
            "retry_permanent_failure",
            record_id=record_id,
            operation_type=rec.operation_type,
            attempts=rec.attempts,
            reason=reason,
        )

    def increment_attempt(self, record_id: str, last_error: str | None = None) -> None:
        """Increment attempt counter and check for max retries."""
        with self._lock:
            rec = self._store.get(record_id)
            if not rec:
                logger.warning("retry_increment_failed_not_found", record_id=record_id)
                return

            rec.attempts += 1
            rec.last_error = last_error
            rec.updated_at = datetime.now(timezone.utc)

            # Check if max attempts reached
            if rec.attempts >= self.config.max_attempts:
                self._mark_permanent_failure_locked(
                    record_id,
                    f"Max retries ({self.config.max_attempts}) exceeded: {last_error}",
                )
            else:
                # Calculate next retry time with exponential backoff
                retry_delay = self._calculate_retry_delay(rec.attempts)
                rec.next_retry_at = datetime.now(timezone.utc) + timedelta(
                    seconds=retry_delay
                )

                # Release claim so it can be retried later
                if record_id in self._claims:
                    del self._claims[record_id]

                logger.info(
                    "retry_scheduled",
                    record_id=record_id,
                    operation_type=rec.operation_type,
                    attempts=rec.attempts,
                    max_attempts=self.config.max_attempts,
                    next_retry_in_seconds=retry_delay,
                )

    def _calculate_retry_delay(self, attempts: int) -> int:
        """Calculate exponential backoff delay in seconds.

        Uses the formula: base_delay * (2 ^ attempts)
        Capped at max_delay_seconds.

        Args:
            attempts: Number of attempts already made

        Returns:
            Delay in seconds before next retry
        """
        delay = self.config.base_delay_seconds * (2**attempts)
        return min(delay, self.config.max_delay_seconds)

    def get_dlq_entries(self) -> List[RetryRecord]:
        """Get all dead letter queue entries (for monitoring).

        Returns:
            List of records that have permanently failed
        """
        with self._lock:
            return list(self._dlq.values())

    def get_stats(self) -> dict:
        """Get retry queue statistics.

        Returns:
            Dictionary with counts of active, claimed, and DLQ records
        """
        with self._lock:
            return {
                "active_records": len(self._store),
                "claimed_records": len(self._claims),
                "dlq_records": len(self._dlq),
            }
