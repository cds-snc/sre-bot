"""Audit trail service for dependency injection.

Wraps the DynamoDB audit storage operations with a service interface.
Delegates all I/O to ``StorageService`` — no direct boto3 or dynamodb_next calls.
"""

from datetime import datetime, timedelta, timezone
from functools import cache
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import structlog

from infrastructure.audit.models import AuditEvent
from infrastructure.audit.protocol import AuditTrailService
from infrastructure.operations.result import OperationResult
from infrastructure.storage import get_storage_service

if TYPE_CHECKING:
    from infrastructure.storage.protocol import StorageService

logger = structlog.get_logger(__name__)

TABLE_NAME = "sre_bot_audit_trail"


def _compute_ttl_timestamp(retention_days: int) -> int:
    expiry = datetime.now(timezone.utc) + timedelta(days=retention_days)
    return int(expiry.timestamp())


class DynamoDBAuditTrailService:
    """DynamoDB implementation of audit trail service for structured event storage and retrieval.

    Uses ``StorageService`` for all DynamoDB I/O so serialization,
    pagination, and error normalisation are handled consistently.

    Usage::

        from infrastructure.audit import AuditTrailServiceDep

        @router.post("/audit/write")
        def write_event(audit_trail: AuditTrailServiceDep, event: AuditEvent):
            success = audit_trail.write_audit_event(event)
            return {"written": success}

    """

    def __init__(self, storage: "StorageService") -> None:
        self._storage = storage
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

        item: Dict[str, Any] = {
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

        result: OperationResult = self._storage.put(TABLE_NAME, item)
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
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit trail for a resource.

        Args:
            resource_id: Partition key (e.g. group email or resource GUID).
            start_time: Optional lower bound (exclusive) on the sort key timestamp.
            end_time: Unused — included for API symmetry; not yet supported.
            limit: Maximum results capped at 100.

        Returns:
            List of deserialized event dicts, newest first.
        """
        key_condition = "resource_id = :rid"
        expression_values: Dict[str, Any] = {":rid": resource_id}

        if start_time:
            key_condition += " AND timestamp_correlation_id < :ts"
            expression_values[":ts"] = start_time.isoformat()

        result = self._storage.query(
            TABLE_NAME,
            key_condition=key_condition,
            expression_values=expression_values,
            Limit=min(limit, 100),
            ScanIndexForward=False,
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
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get audit trail for a user via GSI1 (user_email-timestamp-index).

        Args:
            user_email: User email to query.
            start_time: Optional lower bound on timestamp.
            end_time: Unused — included for API symmetry; not yet supported.
            limit: Maximum results capped at 100.

        Returns:
            List of deserialized event dicts, newest first.
        """
        key_condition = "user_email = :ue"
        expression_values: Dict[str, Any] = {":ue": user_email}

        if start_time:
            key_condition += " AND timestamp < :ts"
            expression_values[":ts"] = start_time.isoformat()

        result = self._storage.query(
            TABLE_NAME,
            key_condition=key_condition,
            expression_values=expression_values,
            IndexName="user_email-timestamp-index",
            Limit=min(limit, 100),
            ScanIndexForward=False,
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
    ) -> Optional[Dict[str, Any]]:
        """Lookup one audit event by correlation ID via GSI2 (correlation_id-index).

        Args:
            correlation_id: The distributed-tracing correlation ID.

        Returns:
            Deserialized event dict if found, None otherwise.
        """
        result = self._storage.query(
            TABLE_NAME,
            key_condition="correlation_id = :cid",
            expression_values={":cid": correlation_id},
            IndexName="correlation_id-index",
            Limit=1,
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
    storage = get_storage_service()
    return DynamoDBAuditTrailService(storage)
