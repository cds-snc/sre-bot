"""Access Sync job and holder status storage.

Wraps ``RecordStore`` for job-status polling and lock-holder metadata used by
the access-sync package. Access Sync owns the record serialization and key
scheme while infrastructure owns DynamoDB transport concerns.

Records are stored as JSON strings in the table shared with the idempotency store (``ACCESS_SYNC_JOB_STATUS_TABLE_NAME``)
to preserve exact primitive types on round-trip.
"""

import json
import time
from typing import Any

import structlog

from contracts.records import KeySchema, RecordStore, RecordTable

logger = structlog.get_logger()

# Shares the table with infrastructure/coordination; only the key attribute is declared here.
JOB_STATUS_KEY = KeySchema(partition="idempotency_key")


def job_status_table(name: str) -> RecordTable:
    """Return the job status key layout bound to the configured table name."""
    return RecordTable(name=name, key=JOB_STATUS_KEY)


class JobStatusStore:
    """DynamoDB-backed status store for access-sync job and holder records."""

    def __init__(self, storage: RecordStore, table_name: str) -> None:
        self._storage = storage
        self._table = job_status_table(table_name)

    def put(self, key: str, record: dict[str, Any], ttl_seconds: int) -> None:
        """Persist a record with TTL. Errors are logged and not propagated."""
        item = {
            "idempotency_key": key,
            "record_json": json.dumps(record),
            "ttl": int(time.time()) + ttl_seconds,
        }
        result = self._storage.put(self._table, item)
        if not result.is_success:
            logger.error("job_status_store_put_failed", key=key, error=result.message)

    def get(self, key: str) -> dict[str, Any] | None:
        """Fetch and deserialize a record. Returns None for misses or malformed data."""
        result = self._storage.get(self._table, {"idempotency_key": key})
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
