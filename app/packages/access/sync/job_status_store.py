"""Access Sync job and holder status storage.

Wraps ``StorageService`` for job-status polling and lock-holder metadata used by
the access-sync package. Access Sync owns the record serialization and key
scheme while infrastructure owns DynamoDB transport concerns.

Records are stored as JSON strings in the shared ``sre_bot_idempotency`` table
to preserve exact primitive types on round-trip.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from infrastructure.storage import StorageService

logger = structlog.get_logger()


class JobStatusStore:
    """DynamoDB-backed status store for access-sync job and holder records."""

    TABLE = "sre_bot_idempotency"

    def __init__(self, storage: StorageService) -> None:
        self._storage = storage

    def put(self, key: str, record: dict[str, Any], ttl_seconds: int) -> None:
        """Persist a record with TTL. Errors are logged and not propagated."""
        item = {
            "idempotency_key": key,
            "record_json": json.dumps(record),
            "ttl": int(time.time()) + ttl_seconds,
        }
        result = self._storage.put(self.TABLE, item)
        if not result.is_success:
            logger.error("job_status_store_put_failed", key=key, error=result.message)

    def get(self, key: str) -> dict[str, Any] | None:
        """Fetch and deserialize a record. Returns None for misses or malformed data."""
        result = self._storage.get(self.TABLE, {"idempotency_key": key})
        if not result.is_success:
            return None

        item = result.data if isinstance(result.data, dict) else None
        if item is None:
            return None

        raw = item.get("record_json")
        if not isinstance(raw, str) or not raw:
            return None

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None

        return parsed if isinstance(parsed, dict) else None
