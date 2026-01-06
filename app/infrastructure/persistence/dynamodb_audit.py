"""DynamoDB persistence layer for audit trail operations.

Provides fast, queryable access to audit events for operational needs
(UI display, API responses) while Sentinel handles long-term compliance storage.

Table schema:
- Partition Key: resource_id (e.g., "engineering@example.com")
- Sort Key: timestamp#correlation_id (allows range queries by time)
- GSI1: user_email-timestamp-index (query by user)
- GSI2: correlation_id-index (query by correlation ID)
- TTL: ttl_timestamp (auto-delete old records after 90 days)
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog
from infrastructure.audit.models import AuditEvent
from integrations.aws import dynamodb_next

logger = structlog.get_logger()

TABLE_NAME = "sre_bot_audit_trail"


def _compute_ttl_timestamp(retention_days: int) -> int:
    """Compute DynamoDB TTL timestamp (Unix epoch seconds).

    Args:
        retention_days: Number of days to retain before auto-deletion.

    Returns:
        Unix timestamp (seconds since epoch) when record should be deleted.
    """
    expiry = datetime.now(timezone.utc) + timedelta(days=retention_days)
    return int(expiry.timestamp())


def write_audit_event(
    audit_event: AuditEvent,
    retention_days: int = 90,
) -> bool:
    """Write audit event to DynamoDB for operational queries.

    This is a non-blocking write that complements the Sentinel SIEM write.
    Records are automatically deleted after retention_days via DynamoDB TTL.

    Args:
        audit_event: The AuditEvent to persist.
        retention_days: Days to retain before auto-deletion (default 90).

    Returns:
        True if write succeeded, False otherwise.

    Note:
        - Never raises exceptions (logs errors and returns False)
        - Non-critical: System continues if write fails
        - Used alongside Sentinel for operational efficiency
    """
    try:
        # Build sort key that allows range queries by timestamp
        sort_key = f"{audit_event.timestamp}#{audit_event.correlation_id}"

        # Get resource_id (primary partitioning key)
        resource_id = audit_event.resource_id or "unknown"

        # Build item with all audit event data (DynamoDB format)
        item = {
            "resource_id": {"S": resource_id},
            "timestamp_correlation_id": {"S": sort_key},
            # Replicate key fields for GSI queries
            "timestamp": {"S": audit_event.timestamp},
            "correlation_id": {"S": audit_event.correlation_id},
            "user_email": {"S": audit_event.user_email},
            "action": {"S": audit_event.action},
            "result": {"S": audit_event.result},
            "resource_type": {"S": audit_event.resource_type},
            # TTL for auto-deletion (Unix timestamp)
            "ttl_timestamp": {"N": str(_compute_ttl_timestamp(retention_days))},
        }

        # Add optional fields if present
        if audit_event.provider:
            item["provider"] = {"S": audit_event.provider}
        if audit_event.error_type:
            item["error_type"] = {"S": audit_event.error_type}
        if audit_event.error_message:
            item["error_message"] = {"S": audit_event.error_message}
        if audit_event.duration_ms is not None:
            item["duration_ms"] = {"N": str(audit_event.duration_ms)}

        # Add all dynamic metadata fields (audit_meta_*) from model
        full_data = audit_event.to_sentinel_payload()
        for key, value in full_data.items():
            if key.startswith("audit_meta_"):
                if value is not None:
                    item[key] = {"S": str(value)}

        # Write to DynamoDB using standardized client
        result = dynamodb_next.put_item(
            table_name=TABLE_NAME,
            Item=item,
        )

        if result.is_success:
            logger.debug(
                "audit_event_written_to_dynamodb",
                resource_id=resource_id,
                action=audit_event.action,
                correlation_id=audit_event.correlation_id,
            )
            return True
        else:
            logger.error(
                "dynamodb_audit_write_error",
                error_message=result.message,
                error_code=result.error_code,
                correlation_id=audit_event.correlation_id,
            )
            return False

    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "unexpected_audit_write_error",
            error=str(e),
            error_type=type(e).__name__,
            correlation_id=audit_event.correlation_id,
        )
        return False


def get_audit_trail(
    resource_id: str,
    limit: int = 50,
    start_timestamp: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query audit trail for a specific resource.

    Returns most recent events first (reverse time order).

    Args:
        resource_id: The resource to query (e.g., group email).
        limit: Maximum number of events to return (max 100).
        start_timestamp: Optional ISO 8601 timestamp to query after.

    Returns:
        List of audit events sorted by timestamp (newest first).
        Returns empty list if resource has no audit trail or on error.
    """
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1

    try:
        # Build key condition expression
        key_condition = "resource_id = :rid"
        expression_values = {":rid": {"S": resource_id}}

        if start_timestamp:
            # Query after a specific timestamp
            key_condition += " AND timestamp_correlation_id < :ts"
            expression_values[":ts"] = {"S": start_timestamp}

        # Query using standardized client
        result = dynamodb_next.query(
            table_name=TABLE_NAME,
            KeyConditionExpression=key_condition,
            ExpressionAttributeValues=expression_values,
            Limit=limit,
            ScanIndexForward=False,  # Descending order by sort key
        )

        if result.is_success:
            items = result.data or []
            logger.debug(
                "audit_trail_queried",
                resource_id=resource_id,
                item_count=len(items),
            )
            return items
        else:
            logger.error(
                "audit_trail_query_error",
                resource_id=resource_id,
                error=result.message,
                error_code=result.error_code,
            )
            return []

    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "audit_trail_query_error",
            resource_id=resource_id,
            error=str(e),
        )
        return []


def get_user_audit_trail(
    user_email: str,
    limit: int = 50,
    start_timestamp: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query audit trail for operations performed by a user.

    Uses GSI to efficiently query by user_email.
    Returns most recent events first (reverse time order).

    Args:
        user_email: The user to query.
        limit: Maximum number of events to return (max 100).
        start_timestamp: Optional ISO 8601 timestamp to query after.

    Returns:
        List of audit events where user_email matches, sorted by timestamp (newest first).
        Returns empty list if user has no audit trail or on error.
    """
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1

    try:
        # Build key condition expression
        key_condition = "user_email = :ue"
        expression_values = {":ue": {"S": user_email}}

        if start_timestamp:
            key_condition += " AND timestamp < :ts"
            expression_values[":ts"] = {"S": start_timestamp}

        # Query GSI1 using standardized client
        result = dynamodb_next.query(
            table_name=TABLE_NAME,
            IndexName="user_email-timestamp-index",
            KeyConditionExpression=key_condition,
            ExpressionAttributeValues=expression_values,
            Limit=limit,
            ScanIndexForward=False,  # Descending order by sort key
        )

        if result.is_success:
            items = result.data or []
            logger.debug(
                "user_audit_trail_queried",
                user_email=user_email,
                item_count=len(items),
            )
            return items
        else:
            logger.error(
                "user_audit_trail_query_error",
                user_email=user_email,
                error=result.message,
                error_code=result.error_code,
            )
            return []

    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "user_audit_trail_query_error",
            user_email=user_email,
            error=str(e),
        )
        return []


def get_by_correlation_id(
    correlation_id: str,
) -> Optional[Dict[str, Any]]:
    """Lookup a single audit event by correlation ID.

    Uses GSI2 (correlation_id-index) for efficient lookup.
    Useful for tracing a complete operation across multiple events.

    Args:
        correlation_id: The correlation ID to lookup.

    Returns:
        The audit event if found, None otherwise.
    """
    try:
        # Query GSI2 using standardized client
        result = dynamodb_next.query(
            table_name=TABLE_NAME,
            IndexName="correlation_id-index",
            KeyConditionExpression="correlation_id = :cid",
            ExpressionAttributeValues={":cid": {"S": correlation_id}},
            Limit=1,  # Should be exactly one per correlation_id
        )

        if result.is_success:
            items = result.data or []
            if items:
                logger.debug(
                    "audit_event_found_by_correlation_id",
                    correlation_id=correlation_id,
                )
                return items[0]

            logger.debug(
                "audit_event_not_found",
                correlation_id=correlation_id,
            )
            return None
        else:
            logger.error(
                "correlation_id_lookup_error",
                correlation_id=correlation_id,
                error=result.message,
                error_code=result.error_code,
            )
            return None

    except Exception as e:  # pylint: disable=broad-except
        logger.error(
            "correlation_id_lookup_error",
            correlation_id=correlation_id,
            error=str(e),
        )
        return None
