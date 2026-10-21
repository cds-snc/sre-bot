"""In-memory ConditionalWriteStore implementation."""

import threading
import time
import uuid
from typing import Any

from contracts.coordination import (
    ClaimOutcome,
    ClaimResult,
    ConditionalWriteStore,
)
from infrastructure.coordination.settings import ConditionalWriteSettings


class InMemoryConditionalWriteStore(ConditionalWriteStore):
    """Thread-safe in-memory conditional-write store.

    This provider mirrors the DynamoDB-backed protocol semantics while keeping
    data local to process memory for deterministic tests and development.
    """

    def __init__(self, settings: ConditionalWriteSettings) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._record_ttl_seconds = settings.idempotency_ttl_seconds
        self._in_progress_ttl_seconds = settings.idempotency_in_progress_ttl_seconds

    def claim(self, key: str) -> ClaimOutcome:
        """Atomically claim key unless it is already in progress or completed."""
        now = int(time.time())

        with self._lock:
            existing = self._store.get(key) or {}
            status = existing.get("status")

            if status == ClaimResult.COMPLETED.name:
                return ClaimOutcome(result=ClaimResult.COMPLETED, outcome=existing.get("outcome"))

            if status == ClaimResult.IN_PROGRESS.name and int(existing.get("in_progress_expires_at", 0)) >= now:
                return ClaimOutcome(result=ClaimResult.IN_PROGRESS)

            claim_token = uuid.uuid4().hex
            self._store[key] = {
                "status": ClaimResult.IN_PROGRESS.name,
                "claim_token": claim_token,
                "claimed_at": now,
                "in_progress_expires_at": now + self._in_progress_ttl_seconds,
                "ttl": now + self._in_progress_ttl_seconds,
            }
            return ClaimOutcome(result=ClaimResult.NEW, claim_token=claim_token)

    def complete(self, key: str, outcome: dict[str, Any], claim_token: str) -> bool:
        """Record the outcome if claim_token still holds the key; the token stays on the record."""
        now = int(time.time())
        with self._lock:
            existing = self._store.get(key)
            if existing is None or existing.get("claim_token") != claim_token:
                return False
            self._store[key] = {
                "status": ClaimResult.COMPLETED.name,
                "claim_token": claim_token,
                "outcome": outcome,
                "completed_at": now,
                "ttl": now + self._record_ttl_seconds,
            }
            return True

    def release(self, key: str, claim_token: str) -> bool:
        """Delete an in-progress record held by claim_token so a redelivery can claim it again."""
        with self._lock:
            existing = self._store.get(key)
            if (
                existing is None
                or existing.get("claim_token") != claim_token
                or existing.get("status") != ClaimResult.IN_PROGRESS.name
            ):
                return False
            del self._store[key]
            return True
