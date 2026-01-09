"""Persistence service for dependency injection.

Provides a class-based interface to the persistence layer for easier DI and testing.
"""

from typing import TYPE_CHECKING, List, Optional
from datetime import datetime

from infrastructure.audit.models import AuditEvent
from infrastructure.persistence.dynamodb_audit import (
    write_audit_event as _write_audit_event,
    get_audit_trail as _get_audit_trail,
    get_user_audit_trail as _get_user_audit_trail,
    get_by_correlation_id as _get_by_correlation_id,
)

if TYPE_CHECKING:
    from infrastructure.configuration import Settings

import structlog

logger = structlog.get_logger(__name__)


class PersistenceService:
    """Persistence service for audit trail and operational data.

    Wraps the DynamoDB persistence layer with a service interface to support
    dependency injection and easier testing with mocks.

    This is a thin facade - all actual work is delegated to the underlying
    module functions in dynamodb_audit.

    Usage:
        # Via dependency injection
        from infrastructure.services import PersistenceServiceDep

        @router.post("/audit/write")
        def write_event(
            persistence: PersistenceServiceDep,
            event: AuditEvent
        ):
            success = persistence.write_audit_event(event)
            return {"written": success}

        # Direct instantiation
        from infrastructure.services import get_settings
        from infrastructure.persistence import PersistenceService

        settings = get_settings()
        service = PersistenceService(settings)
        success = service.write_audit_event(event)
    """

    def __init__(self, settings: "Settings"):
        """Initialize persistence service.

        Args:
            settings: Settings instance (required, passed from provider).
        """
        self._settings = settings
        logger.info("initialized_persistence_service")

    def write_audit_event(
        self,
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
        return _write_audit_event(audit_event, retention_days)

    def get_audit_trail(
        self,
        resource_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get audit trail for a resource with optional time range.

        Args:
            resource_id: The resource identifier (e.g., group email)
            start_time: Optional start of time range (inclusive)
            end_time: Optional end of time range (inclusive)
            limit: Maximum number of results (default 100, max 1000)

        Returns:
            List of AuditEvent objects, newest first

        Note:
            Returns empty list on errors (logs and continues)
        """
        return _get_audit_trail(resource_id, start_time, end_time, limit)

    def get_user_audit_trail(
        self,
        user_email: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get audit trail for a user with optional time range.

        Uses GSI1 (user_email-timestamp-index) for efficient lookups.

        Args:
            user_email: The user's email address
            start_time: Optional start of time range (inclusive)
            end_time: Optional end of time range (inclusive)
            limit: Maximum number of results (default 100, max 1000)

        Returns:
            List of AuditEvent objects, newest first

        Note:
            Returns empty list on errors (logs and continues)
        """
        return _get_user_audit_trail(user_email, start_time, end_time, limit)

    def get_by_correlation_id(
        self,
        correlation_id: str,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get audit events by correlation ID.

        Uses GSI2 (correlation_id-index) to retrieve all events in a logical operation.

        Args:
            correlation_id: The correlation ID to search for
            limit: Maximum number of results (default 100, max 1000)

        Returns:
            List of AuditEvent objects matching the correlation ID

        Note:
            Returns empty list on errors (logs and continues)
        """
        return _get_by_correlation_id(correlation_id, limit)
