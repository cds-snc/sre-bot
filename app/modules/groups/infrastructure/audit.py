"""Audit logging for group operations.

.. deprecated::
    This module is deprecated and will be removed. All audit logging
    has been moved to the centralized infrastructure.events system with automatic
    audit event generation and Sentinel integration.

    **Migration Guide:**
    - The central audit handler (infrastructure.events.handlers.audit) now handles
      all audit events automatically when events are dispatched
    - Remove calls to AuditEntry.create() and write_audit_entry()
    - Update event handlers to only focus on business logic
    - Events dispatched via infrastructure.events.dispatch_event() are
      automatically audited

    For backward compatibility, this module remains available but should not be
    used for new code. All existing code will continue to work until Phase 4.

Provides structured audit logging with support for:
- Stage 1: Synchronous writes to Sentinel and structured logs
- Stage 2: Synchronous writes to DynamoDB with TTL (future implementation)

All group operations should generate audit entries for compliance.
Audit entries are written synchronously to ensure a guaranteed audit trail.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from core.logging import get_module_logger
from integrations.sentinel import client as sentinel_client

logger = get_module_logger()


class AuditEntry(BaseModel):
    """Structured audit entry for group operations.

    Attributes:
        correlation_id: Unique ID for this request (for tracing)
        timestamp: ISO 8601 timestamp of operation
        action: Operation type (add_member, remove_member, etc.)
        group_id: Group identifier
        member_email: Member email (if applicable)
        provider: Provider name (google, aws, etc.)
        success: Whether operation succeeded
        requestor: User who initiated the operation
        justification: Justification provided by requestor
        error_message: Error message if operation failed
        metadata: Additional operation-specific data
        ttl_seconds: TTL for DynamoDB (Stage 2 only)
    """

    correlation_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    action: str
    group_id: str
    member_email: Optional[str] = None
    provider: str
    success: bool
    requestor: Optional[str] = None
    justification: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ttl_seconds: int = Field(default=7776000)  # 90 days

    @property
    def is_success(self) -> bool:
        """Alias for success field for consistency with OperationResult.is_success."""
        return self.success

    class Config:
        json_schema_extra = {
            "example": {
                "correlation_id": "req-123-456",
                "timestamp": "2025-01-08T12:00:00Z",
                "action": "add_member",
                "group_id": "engineering@company.com",
                "member_email": "alice@company.com",
                "provider": "google",
                "success": True,
                "requestor": "bob@company.com",
                "justification": "Alice joining engineering team",
                "metadata": {"propagation_count": 2},
            }
        }


def write_audit_entry(entry: AuditEntry) -> None:
    """Write audit entry to Sentinel and structured logs.

    Stage 1: Writes to both Sentinel (via integration client) and structlog
    Stage 2: Will also write to DynamoDB

    This function is synchronous and blocks until audit is written.

    Args:
        entry: AuditEntry to write
    """
    # Prepare audit data for logging
    audit_data = {
        "correlation_id": entry.correlation_id,
        "timestamp": entry.timestamp,
        "action": entry.action,
        "group_id": entry.group_id,
        "member_email": entry.member_email,
        "provider": entry.provider,
        "success": entry.success,
        "requestor": entry.requestor,
        "justification": entry.justification,
        "error_message": entry.error_message,
        "metadata": entry.metadata,
    }

    # Stage 1a: Write to structured logs (local logging)
    logger.info("audit_entry", **audit_data)

    # Stage 1b: Send to Sentinel (external audit trail)
    try:
        sentinel_client.log_to_sentinel(
            event="group_membership_audit", message=audit_data
        )
    except Exception as e:
        # Don't fail the operation if Sentinel is unavailable
        # Log the error but continue (audit is already in structlog)
        logger.error(
            "sentinel_audit_write_failed",
            error=str(e),
            correlation_id=entry.correlation_id,
            action=entry.action,
        )

    # Stage 2: Will add DynamoDB write here
    # _write_to_dynamodb(entry)


def create_audit_entry_from_operation(
    correlation_id: str,
    action: str,
    group_id: str,
    provider: str,
    success: bool,
    requestor: Optional[str] = None,
    member_email: Optional[str] = None,
    justification: Optional[str] = None,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditEntry:
    """Factory function to create audit entries from operation results.

    Args:
        correlation_id: Request correlation ID for tracing
        action: Operation type (add_member, remove_member, list_groups, etc.)
        group_id: Group identifier
        provider: Provider name
        success: Whether operation succeeded
        requestor: User who initiated operation
        member_email: Member email (for add/remove operations)
        justification: Justification provided by requestor
        error_message: Error message if operation failed
        metadata: Additional operation-specific data

    Returns:
        AuditEntry ready to write
    """
    return AuditEntry(
        correlation_id=correlation_id,
        action=action,
        group_id=group_id,
        member_email=member_email,
        provider=provider,
        success=success,
        requestor=requestor,
        justification=justification,
        error_message=error_message,
        metadata=metadata or {},
    )


def get_audit_trail(group_id: str, limit: int = 50) -> list:
    """Get audit trail for a specific group (placeholder for Stage 2)."""
    logger.info(f"Retrieving audit trail for group {group_id} (limit: {limit})")
    return []


def get_user_audit_trail(user_email: str, limit: int = 50) -> list:
    """Get audit trail for a specific user's group actions (placeholder for Stage 2)."""
    logger.info(f"Retrieving audit trail for user {user_email} (limit: {limit})")
    return []
