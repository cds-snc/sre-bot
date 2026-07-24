"""In-memory IdempotencyStore implementation."""

import threading
import time
from typing import Any

from infrastructure.idempotency.protocol import (
    ClaimOutcome,
    ClaimResult,
    IdempotencyStore,
)
from infrastructure.idempotency.settings import IdempotencySettings


class InMemoryIdempotencyStore(IdempotencyStore):
    """Thread-safe in-memory idempotency store.

    This provider mirrors the DynamoDB-backed protocol semantics while keeping
    data local to process memory for deterministic tests and development.
    """

    def __init__(self, idempotency_settings: IdempotencySettings) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._record_ttl_seconds = idempotency_settings.IDEMPOTENCY_TTL_SECONDS
        self._in_progress_ttl_seconds = idempotency_settings.IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS

    def claim(self, key: str) -> ClaimOutcome:
        """Atomically claim key unless it is already in progress or completed."""
        now = int(time.time())

        with self._lock:
            existing = self._store.get(key)

            if existing is None:
                self._store[key] = self._new_in_progress_record(now)
                return ClaimOutcome(result=ClaimResult.NEW)

            status = existing.get("status")

            if status == ClaimResult.COMPLETED.name:
                return ClaimOutcome(result=ClaimResult.COMPLETED, outcome=existing.get("outcome"))

            if status == ClaimResult.IN_PROGRESS.name:
                expires_at = int(existing.get("in_progress_expires_at", 0))
                if expires_at < now:
                    self._store[key] = self._new_in_progress_record(now)
                    return ClaimOutcome(result=ClaimResult.NEW)
                return ClaimOutcome(result=ClaimResult.IN_PROGRESS)

            self._store[key] = self._new_in_progress_record(now)
            return ClaimOutcome(result=ClaimResult.NEW)

    def complete(self, key: str, outcome: dict[str, Any]) -> None:
        """Record completed execution outcome for the key."""
        now = int(time.time())
        with self._lock:
            self._store[key] = {
                "status": ClaimResult.COMPLETED.name,
                "outcome": outcome,
                "completed_at": now,
                "ttl": now + self._record_ttl_seconds,
            }

    def release(self, key: str) -> None:
        """Delete key record so a redelivery can claim it again."""
        with self._lock:
            self._store.pop(key, None)

    def _new_in_progress_record(self, now: int) -> dict[str, Any]:
        return {
            "status": ClaimResult.IN_PROGRESS.name,
            "claimed_at": now,
            "in_progress_expires_at": now + self._in_progress_ttl_seconds,
            "ttl": now + self._in_progress_ttl_seconds,
        }
