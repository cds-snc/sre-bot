"""Tests for AuditTrailService Protocol contract and implementation.

Verifies:
- Protocol has @runtime_checkable
- DynamoDBAuditTrailService satisfies the Protocol
- Fake implementations can be injected
- DI override works for testing
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from infrastructure.audit.models import AuditEvent
from infrastructure.audit.protocol import AuditTrailService
from infrastructure.audit.service import DynamoDBAuditTrailService
from infrastructure.operations.result import OperationResult
from infrastructure.storage.protocol import StorageService


class FakeAuditTrailService:
    """Fake in-memory audit trail for testing."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def write_audit_event(
        self,
        audit_event: AuditEvent,
        retention_days: int = 90,
    ) -> bool:
        """Write event to fake store."""
        self._events.append(
            {
                "resource_id": audit_event.resource_id,
                "timestamp": audit_event.timestamp,
                "action": audit_event.action,
            }
        )
        return True

    def get_audit_trail(
        self,
        resource_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get audit trail for resource."""
        return [e for e in self._events if e["resource_id"] == resource_id][:limit]

    def get_user_audit_trail(
        self,
        user_email: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get audit trail for user."""
        return []

    def get_by_correlation_id(
        self,
        correlation_id: str,
    ) -> dict[str, Any] | None:
        """Get event by correlation ID."""
        return None


def test_protocol_is_runtime_checkable() -> None:
    """AuditTrailService Protocol has @runtime_checkable."""
    assert hasattr(AuditTrailService, "_is_runtime_protocol")


def test_dynamodb_audit_satisfies_protocol() -> None:
    """DynamoDBAuditTrailService satisfies AuditTrailService Protocol."""
    mock_storage = MagicMock(spec=StorageService)
    mock_storage.put.return_value = OperationResult.success(data=None)

    impl = DynamoDBAuditTrailService(storage=mock_storage)
    assert isinstance(impl, AuditTrailService)


def test_fake_audit_satisfies_protocol() -> None:
    """In-memory fake satisfies AuditTrailService Protocol."""
    fake = FakeAuditTrailService()
    assert isinstance(fake, AuditTrailService)


def test_audit_dep_override_with_fake() -> None:
    """Dependency override with fake implementation works."""
    # This is a structure test — verifies that the Protocol type
    # allows duck-typing and DI override in tests
    fake = FakeAuditTrailService()

    event = AuditEvent(
        resource_id="test-group",
        timestamp=datetime.now(UTC).isoformat(),
        correlation_id="corr-123",
        user_email="user@example.com",
        action="CREATE",
        result="success",
    )

    # Verify the fake can be used as a drop-in replacement
    written = fake.write_audit_event(event)
    assert written is True

    trail = fake.get_audit_trail("test-group")
    assert len(trail) == 1
    assert trail[0]["action"] == "CREATE"


def test_protocol_has_write_audit_event_method() -> None:
    """AuditTrailService Protocol defines write_audit_event."""
    assert hasattr(AuditTrailService, "write_audit_event")


def test_protocol_has_get_audit_trail_method() -> None:
    """AuditTrailService Protocol defines get_audit_trail."""
    assert hasattr(AuditTrailService, "get_audit_trail")


def test_protocol_has_get_user_audit_trail_method() -> None:
    """AuditTrailService Protocol defines get_user_audit_trail."""
    assert hasattr(AuditTrailService, "get_user_audit_trail")


def test_protocol_has_get_by_correlation_id_method() -> None:
    """AuditTrailService Protocol defines get_by_correlation_id."""
    assert hasattr(AuditTrailService, "get_by_correlation_id")
