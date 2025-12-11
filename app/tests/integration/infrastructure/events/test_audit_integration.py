"""Integration tests for audit event handler with event system.

Tests end-to-end flow: Event dispatched → audit handler processes →
AuditEvent created → Sentinel client called (mocked).
"""

from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock

import pytest

from infrastructure.events import (
    Event,
    dispatch_event,
    register_event_handler,
    clear_handlers,
)
from infrastructure.events.handlers.audit import handle_audit_event
from infrastructure.audit.models import AuditEvent


@pytest.mark.integration
class TestAuditHandlerEventDispatch:
    """Integration tests for audit handler with event dispatcher."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear handlers before each test."""
        clear_handlers()
        yield
        clear_handlers()

    def test_audit_handler_receives_dispatched_event(self, monkeypatch):
        """Audit handler receives events when registered and dispatched."""
        # Register audit handler for specific event type
        register_event_handler("test.action")(handle_audit_event)

        # Mock the sentinel client to capture calls
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        # Dispatch an event
        event = Event(
            event_type="test.action",
            correlation_id=uuid4(),
            user_email="alice@example.com",
            metadata={"success": True, "custom_field": "value"},
        )
        dispatch_event(event)

        # Verify audit event was created and logged
        assert mock_sentinel.called

    def test_audit_handler_wildcard_registration(self, monkeypatch):
        """Audit handler registered for * receives all events."""
        # Register audit handler as wildcard for all events
        register_event_handler("*")(handle_audit_event)

        # Mock the sentinel client to capture calls
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        # Dispatch different event types
        for event_type in [
            "group.member.added",
            "incident.created",
            "webhook.received",
        ]:
            event = Event(
                event_type=event_type,
                correlation_id=uuid4(),
                user_email="alice@example.com",
                metadata={"success": True},
            )
            dispatch_event(event)

        # Verify audit event was logged for each event
        assert mock_sentinel.call_count == 3

    def test_audit_handler_with_other_handlers(self, monkeypatch):
        """Audit handler works alongside other handlers."""
        # Create a mock business handler
        mock_business_handler = Mock()

        # Register both handlers for the same event
        register_event_handler("group.member.added")(mock_business_handler)
        register_event_handler("group.member.added")(handle_audit_event)

        # Mock the sentinel client to capture calls
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        event = Event(
            event_type="group.member.added",
            correlation_id=uuid4(),
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
            },
        )
        dispatch_event(event)

        # Both handlers should be called
        assert mock_business_handler.called
        assert mock_sentinel.called

    def test_audit_handler_converts_group_event_to_audit_event(self, monkeypatch):
        """Audit handler properly converts group events to audit events."""
        register_event_handler("group.member.added")(handle_audit_event)

        # Mock the sentinel client to capture calls
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "provider": "google",
                "success": True,
                "orchestration": {"member_email": "bob@example.com"},
            },
        )
        dispatch_event(event)

        # Verify AuditEvent was created with correct fields
        audit_event: AuditEvent = mock_sentinel.call_args[0][0]
        assert audit_event.action == "group_member_added"
        assert audit_event.resource_type == "group"
        assert audit_event.resource_id == "eng@example.com"
        assert audit_event.result == "success"
        assert audit_event.provider == "google"
        assert audit_event.user_email == "alice@example.com"
        assert str(correlation_id) == audit_event.correlation_id

    def test_audit_handler_converts_incident_event_to_audit_event(self, monkeypatch):
        """Audit handler properly converts incident events to audit events."""
        register_event_handler("incident.created")(handle_audit_event)

        # Mock the sentinel client to capture calls
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        event = Event(
            event_type="incident.created",
            correlation_id=uuid4(),
            user_email="oncall@example.com",
            metadata={
                "incident_id": "INC-12345",
                "provider": "opsgenie",
                "success": True,
            },
        )
        dispatch_event(event)

        audit_event = mock_sentinel.call_args[0][0]
        assert audit_event.action == "incident_created"
        assert audit_event.resource_type == "incident"
        assert audit_event.resource_id == "INC-12345"


@pytest.mark.integration
class TestAuditEventCreation:
    """Integration tests for audit event creation from dispatched events."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear handlers before each test."""
        clear_handlers()
        yield
        clear_handlers()

    def test_audit_event_has_required_fields(self, monkeypatch):
        """Audit event created from dispatched event has all required fields."""
        register_event_handler("*")(handle_audit_event)

        # Mock the sentinel client to capture calls
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        now = datetime.now()
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            timestamp=now,
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
            },
        )
        dispatch_event(event)

        audit_event = mock_sentinel.call_args[0][0]

        # Verify all required fields
        assert audit_event.correlation_id
        assert audit_event.timestamp
        assert audit_event.action
        assert audit_event.resource_type
        assert audit_event.resource_id
        assert audit_event.user_email
        assert audit_event.result in ("success", "failure")

    def test_audit_event_captures_failure_details(self, monkeypatch):
        """Audit event captures error details from failed events."""
        register_event_handler("*")(handle_audit_event)

        # Mock the sentinel client to capture calls
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        event = Event(
            event_type="group.member.added",
            correlation_id=uuid4(),
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": False,
                "error_type": "permission_denied",
                "error_message": "User does not have permission",
            },
        )
        dispatch_event(event)

        audit_event = mock_sentinel.call_args[0][0]
        assert audit_event.result == "failure"
        assert audit_event.error_type == "permission_denied"
        assert audit_event.error_message == "User does not have permission"

    def test_audit_event_flattens_metadata(self, monkeypatch):
        """Audit event flattens custom metadata with audit_meta_ prefix."""
        register_event_handler("*")(handle_audit_event)

        # Mock the sentinel client to capture calls
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        event = Event(
            event_type="group.member.added",
            correlation_id=uuid4(),
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
                "retry_count": 3,
                "request_duration_ms": 150,
            },
        )
        dispatch_event(event)

        audit_event = mock_sentinel.call_args[0][0]
        payload = audit_event.to_sentinel_payload()

        # Verify custom fields are flattened
        assert "audit_meta_retry_count" in payload
        assert "audit_meta_request_duration_ms" in payload


@pytest.mark.integration
class TestSentinelIntegration:
    """Integration tests for Sentinel client integration."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Clear handlers before each test."""
        clear_handlers()
        yield
        clear_handlers()

    def test_sentinel_log_audit_event_called_with_audit_event(self, monkeypatch):
        """Sentinel's log_audit_event is called with AuditEvent instance."""
        register_event_handler("*")(handle_audit_event)

        # Mock the sentinel client to capture calls
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        event = Event(
            event_type="group.member.added",
            correlation_id=uuid4(),
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
            },
        )
        dispatch_event(event)

        # Verify log_audit_event was called
        assert mock_sentinel.called
        # Verify it was called with an AuditEvent
        call_args = mock_sentinel.call_args[0]
        assert isinstance(call_args[0], AuditEvent)

    def test_audit_handler_logs_errors_when_sentinel_fails(self, monkeypatch):
        """Audit handler logs errors but doesn't fail when Sentinel fails."""
        register_event_handler("*")(handle_audit_event)

        # Mock the sentinel client to fail
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        mock_sentinel.side_effect = Exception("Sentinel connection error")
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        # Also patch the logger to verify error logging
        mock_logger = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.logger",
            mock_logger,
            raising=False,
        )

        event = Event(
            event_type="group.member.added",
            correlation_id=uuid4(),
            user_email="alice@example.com",
            metadata={"success": True},
        )
        # Should not raise
        dispatch_event(event)

        # Error should be logged but dispatch should continue
        assert mock_logger.error.called

    def test_multiple_events_audit_trail(self, monkeypatch):
        """Multiple events create corresponding audit trail entries."""
        register_event_handler("*")(handle_audit_event)

        # Mock the sentinel client to capture calls
        from unittest.mock import MagicMock

        mock_sentinel = MagicMock()
        monkeypatch.setattr(
            "infrastructure.events.handlers.audit.sentinel_client.log_audit_event",
            mock_sentinel,
            raising=False,
        )

        # Dispatch multiple events
        events = [
            Event(
                event_type="group.member.added",
                correlation_id=uuid4(),
                user_email="alice@example.com",
                metadata={"group_id": "eng@example.com", "success": True},
            ),
            Event(
                event_type="group.member.removed",
                correlation_id=uuid4(),
                user_email="bob@example.com",
                metadata={"group_id": "eng@example.com", "success": True},
            ),
            Event(
                event_type="incident.created",
                correlation_id=uuid4(),
                user_email="oncall@example.com",
                metadata={"incident_id": "INC-123", "success": True},
            ),
        ]

        for event in events:
            dispatch_event(event)

        # Verify each event was audited
        assert mock_sentinel.call_count == 3

        # Verify each audit event has correct action
        audit_events = [call[0][0] for call in mock_sentinel.call_args_list]
        actions = [ae.action for ae in audit_events]
        assert "group_member_added" in actions
        assert "group_member_removed" in actions
        assert "incident_created" in actions
