"""Protocol contract for audit trail services.

Defines the runtime-checkable interface for audit event storage and retrieval.
Concrete implementations can vary by backing store (DynamoDB, CloudWatch Logs, etc.).
"""

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from infrastructure.audit.models import AuditEvent


@runtime_checkable
class AuditTrailService(Protocol):
    """Audit trail operations abstracted over the backing store."""

    def write_audit_event(
        self,
        audit_event: AuditEvent,
        retention_days: int = 90,
    ) -> bool:
        """Write an audit event to persistent storage.

        Args:
            audit_event: The structured event to persist (AuditEvent model).
            retention_days: DynamoDB TTL retention window (default 90 days).

        Returns:
            True if the write succeeded, False otherwise.
        """
        ...

    def get_audit_trail(
        self,
        resource_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get audit trail for a resource.

        Args:
            resource_id: Partition key (e.g. group email or resource GUID).
            start_time: Optional lower bound on sort key.
            end_time: Unused — included for API symmetry.
            limit: Maximum results capped at 100.

        Returns:
            List of deserialized event dicts, newest first.
        """
        ...

    def get_user_audit_trail(
        self,
        user_email: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get audit trail for a user via GSI (user_email-timestamp-index).

        Args:
            user_email: User email to query.
            start_time: Optional lower bound on timestamp.
            end_time: Unused — included for API symmetry.
            limit: Maximum results capped at 100.

        Returns:
            List of deserialized event dicts, newest first.
        """
        ...

    def get_by_correlation_id(
        self,
        correlation_id: str,
    ) -> dict[str, Any] | None:
        """Lookup one audit event by correlation ID via GSI (correlation_id-index).

        Args:
            correlation_id: The distributed-tracing correlation ID.

        Returns:
            Deserialized event dict if found, None otherwise.
        """
        ...
