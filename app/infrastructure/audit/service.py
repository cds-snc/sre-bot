"""Audit trail service for dependency injection.

Wraps the DynamoDB audit storage operations with a service interface.
Delegates all I/O to ``RecordStore`` — no direct boto3 calls.
"""

from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any

import structlog

from contracts.operations.result import OperationResult
from contracts.records import (
    KeySchema,
    RecordIndex,
    RecordQuery,
    RecordStore,
    RecordTable,
    SortCondition,
    SortOperator,
    SortOrder,
)
from infrastructure.audit.models import AuditEvent
from infrastructure.audit.protocol import MAX_QUERY_LIMIT, AuditTrailService
from infrastructure.audit.settings import get_audit_settings
from infrastructure.records import get_record_store

logger = structlog.get_logger(__name__)

AUDIT_KEY = KeySchema(partition="resource_id", sort="timestamp_correlation_id")
AUDIT_INDEXES = {
    "by_user": RecordIndex(
        physical_name="user_email-timestamp-index",
        key=KeySchema(partition="user_email", sort="timestamp"),
    ),
    "by_correlation": RecordIndex(
        physical_name="correlation_id-index",
        key=KeySchema(partition="correlation_id"),
    ),
}


def audit_table(name: str) -> RecordTable:
    """Return the audit trail's key layout bound to the configured table name."""
    return RecordTable(name=name, key=AUDIT_KEY, indexes=AUDIT_INDEXES)


def _before(start_time: datetime | None) -> SortCondition | None:
    return SortCondition(SortOperator.LT, start_time.isoformat()) if start_time else None


def _compute_ttl_timestamp(retention_days: int) -> int:
    expiry = datetime.now(UTC) + timedelta(days=retention_days)
    return int(expiry.timestamp())


class DynamoDBAuditTrailService:
    """DynamoDB implementation of audit trail service for structured event storage and retrieval.

    Uses ``RecordStore`` for all DynamoDB I/O so serialization,
    pagination, and error normalisation are handled consistently.

    Usage::

        from infrastructure.audit import AuditTrailServiceDep

        @router.post("/audit/write")
        def write_event(audit_trail: AuditTrailServiceDep, event: AuditEvent):
            success = audit_trail.write_audit_event(event)
            return {"written": success}

    """

    def __init__(self, storage: RecordStore, table_name: str) -> None:
        self._storage = storage
        self._table = audit_table(table_name)
        logger.info("initialized_audit_trail_service")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_audit_event(
        self,
        audit_event: AuditEvent,
        retention_days: int = 90,
    ) -> bool:
        """Write an audit event to DynamoDB.

        Non-blocking: returns False on failure rather than raising.

        Args:
            audit_event: The structured event to persist.
            retention_days: DynamoDB TTL retention window (default 90 days).

        Returns:
            True if the write succeeded, False otherwise.
        """
        resource_id = audit_event.resource_id or "unknown"
        sort_key = f"{audit_event.timestamp}#{audit_event.correlation_id}"

        item: dict[str, Any] = {
            "resource_id": resource_id,
            "timestamp_correlation_id": sort_key,
            "timestamp": audit_event.timestamp,
            "correlation_id": audit_event.correlation_id,
            "user_email": audit_event.user_email,
            "action": audit_event.action,
            "result": audit_event.result,
            "ttl_timestamp": _compute_ttl_timestamp(retention_days),
        }

        # Optional fields — only include when present
        if audit_event.resource_type:
            item["resource_type"] = audit_event.resource_type
        if audit_event.provider:
            item["provider"] = audit_event.provider
        if audit_event.error_type:
            item["error_type"] = audit_event.error_type
        if audit_event.error_message:
            item["error_message"] = audit_event.error_message
        if audit_event.duration_ms is not None:
            item["duration_ms"] = audit_event.duration_ms

        # Flatten dynamic audit_meta_* fields from the Sentinel payload
        for key, value in audit_event.to_sentinel_payload().items():
            if key.startswith("audit_meta_") and value is not None:
                item[key] = str(value)

        result: OperationResult = self._storage.put(self._table, item)
        if result.is_success:
            logger.debug(
                "audit_event_written",
                resource_id=resource_id,
                action=audit_event.action,
                correlation_id=audit_event.correlation_id,
            )
            return True

        logger.error(
            "audit_event_write_failed",
            resource_id=resource_id,
            action=audit_event.action,
            error=result.message,
            error_code=result.error_code,
        )
        return False

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_audit_trail(
        self,
        resource_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = MAX_QUERY_LIMIT,
    ) -> list[dict[str, Any]]:
        """Get audit trail for a resource.

        Args:
            resource_id: Partition key (e.g. group email or resource GUID).
            start_time: Optional exclusive upper bound: only events strictly
                before this timestamp are returned (pages backwards in time).
            end_time: Unused — included for API symmetry; not yet supported.
            limit: Maximum results, capped at ``MAX_QUERY_LIMIT`` (100).

        Returns:
            List of deserialized event dicts, newest first.
        """
        result = self._storage.query(
            self._table,
            RecordQuery(
                partition=resource_id,
                sort=_before(start_time),
                limit=min(limit, MAX_QUERY_LIMIT),
                order=SortOrder.DESC,
            ),
        )
        if result.is_success:
            return result.data or []
        logger.error(
            "audit_trail_query_failed",
            resource_id=resource_id,
            error=result.message,
        )
        return []

    def get_user_audit_trail(
        self,
        user_email: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = MAX_QUERY_LIMIT,
    ) -> list[dict[str, Any]]:
        """Get audit trail for a user via GSI1 (user_email-timestamp-index).

        Args:
            user_email: User email to query.
            start_time: Optional exclusive upper bound: only events strictly
                before this timestamp are returned.
            end_time: Unused — included for API symmetry; not yet supported.
            limit: Maximum results, capped at ``MAX_QUERY_LIMIT`` (100).

        Returns:
            List of deserialized event dicts, newest first.
        """
        result = self._storage.query(
            self._table,
            RecordQuery(
                partition=user_email,
                index="by_user",
                sort=_before(start_time),
                limit=min(limit, MAX_QUERY_LIMIT),
                order=SortOrder.DESC,
            ),
        )
        if result.is_success:
            return result.data or []
        logger.error(
            "user_audit_trail_query_failed",
            user_email=user_email,
            error=result.message,
        )
        return []

    def get_by_correlation_id(
        self,
        correlation_id: str,
    ) -> dict[str, Any] | None:
        """Lookup one audit event by correlation ID via GSI2 (correlation_id-index).

        Args:
            correlation_id: The distributed-tracing correlation ID.

        Returns:
            Deserialized event dict if found, None otherwise.
        """
        result = self._storage.query(
            self._table,
            RecordQuery(partition=correlation_id, index="by_correlation", limit=1),
        )
        if result.is_success:
            items = result.data or []
            return items[0] if items else None
        logger.error(
            "correlation_id_lookup_failed",
            correlation_id=correlation_id,
            error=result.message,
        )
        return None


@cache
def get_audit_trail_service() -> AuditTrailService:
    """Get application-scoped audit trail service singleton.
    Returns an AuditTrailService Protocol instance for writing and querying audit
    events. The implementation uses DynamoDB, but can be swapped for alternative
    audit backends that satisfy the Protocol.
    """
    return DynamoDBAuditTrailService(get_record_store(), table_name=get_audit_settings().audit_table_name)
