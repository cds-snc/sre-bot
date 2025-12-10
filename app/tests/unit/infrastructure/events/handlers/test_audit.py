"""Unit tests for audit event handler.

Tests the conversion of infrastructure events to audit events and mocked
Sentinel integration.
"""

from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch

import pytest

from infrastructure.events.models import Event
from infrastructure.events.handlers.audit import (
    AuditHandler,
    handle_audit_event,
    _extract_resource_info,
    _extract_provider,
    _extract_justification,
    _is_success,
)
from infrastructure.audit.models import AuditEvent


@pytest.mark.unit
class TestExtractResourceInfo:
    """Tests for resource information extraction."""

    def test_extract_group_resource_info_with_group_id(self):
        """Extract group resource type and group_id."""
        metadata = {"group_id": "eng@example.com"}
        resource_type, resource_id = _extract_resource_info(
            "group.member.added", metadata
        )
        assert resource_type == "group"
        assert resource_id == "eng@example.com"

    def test_extract_group_resource_info_with_group_email(self):
        """Fall back to group_email if group_id not present."""
        metadata = {"group_email": "eng@example.com"}
        resource_type, resource_id = _extract_resource_info(
            "group.member.added", metadata
        )
        assert resource_type == "group"
        assert resource_id == "eng@example.com"

    def test_extract_incident_resource_info(self):
        """Extract incident resource type and incident_id."""
        metadata = {"incident_id": "inc-123"}
        resource_type, resource_id = _extract_resource_info(
            "incident.created", metadata
        )
        assert resource_type == "incident"
        assert resource_id == "inc-123"

    def test_extract_webhook_resource_info(self):
        """Extract webhook resource type and webhook_id."""
        metadata = {"webhook_id": "wh-456"}
        resource_type, resource_id = _extract_resource_info(
            "webhook.received", metadata
        )
        assert resource_type == "webhook"
        assert resource_id == "wh-456"

    def test_extract_generic_resource_info(self):
        """Fall back to generic resource_type/resource_id."""
        metadata = {"resource_type": "custom", "resource_id": "custom-123"}
        resource_type, resource_id = _extract_resource_info("custom.action", metadata)
        assert resource_type == "custom"
        assert resource_id == "custom-123"

    def test_extract_resource_info_missing_returns_none(self):
        """Return None when resource info not in metadata."""
        metadata = {}
        resource_type, resource_id = _extract_resource_info("unknown.event", metadata)
        assert resource_type is None
        assert resource_id is None


@pytest.mark.unit
class TestExtractProvider:
    """Tests for provider extraction."""

    def test_extract_provider_from_metadata(self):
        """Extract provider from top-level metadata."""
        metadata = {"provider": "google"}
        provider = _extract_provider(metadata)
        assert provider == "google"

    def test_extract_provider_from_orchestration(self):
        """Extract provider from orchestration object."""
        metadata = {"orchestration": {"provider": "aws"}}
        provider = _extract_provider(metadata)
        assert provider == "aws"

    def test_extract_provider_from_request(self):
        """Extract provider from request object."""
        metadata = {"request": {"provider": "slack"}}
        provider = _extract_provider(metadata)
        assert provider == "slack"

    def test_extract_provider_precedence(self):
        """Provider in metadata takes precedence over orchestration."""
        metadata = {
            "provider": "google",
            "orchestration": {"provider": "aws"},
        }
        provider = _extract_provider(metadata)
        assert provider == "google"

    def test_extract_provider_missing_returns_none(self):
        """Return None when provider not in metadata."""
        metadata = {}
        provider = _extract_provider(metadata)
        assert provider is None


@pytest.mark.unit
class TestIsSuccess:
    """Tests for success determination."""

    def test_is_success_explicit_true(self):
        """Determine success from explicit success field."""
        metadata = {"success": True}
        assert _is_success(metadata) is True

    def test_is_success_explicit_false(self):
        """Determine failure from explicit success field."""
        metadata = {"success": False}
        assert _is_success(metadata) is False

    def test_is_success_from_result_string(self):
        """Determine success from result string."""
        metadata = {"result": "success"}
        assert _is_success(metadata) is True

        metadata = {"result": "failure"}
        assert _is_success(metadata) is False

    def test_is_success_from_orchestration(self):
        """Infer success from orchestration object."""
        metadata = {"orchestration": {"success": True}}
        assert _is_success(metadata) is True

        metadata = {"orchestration": {"success": False}}
        assert _is_success(metadata) is False

    def test_is_success_default_true(self):
        """Default to success if no failure indicators."""
        metadata = {}
        assert _is_success(metadata) is True


@pytest.mark.unit
class TestAuditHandlerEventConversion:
    """Tests for converting events to audit events."""

    def test_handle_group_member_added_success(self):
        """Convert successful group member added event."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "provider": "google",
                "success": True,
                "orchestration": {
                    "action": "add_member",
                    "member_email": "bob@example.com",
                },
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        # Verify log_audit_event was called
        assert mock_sentinel.log_audit_event.called
        audit_event = mock_sentinel.log_audit_event.call_args[0][0]

        # Verify audit event fields
        assert isinstance(audit_event, AuditEvent)
        assert audit_event.action == "group_member_added"
        assert audit_event.resource_type == "group"
        assert audit_event.resource_id == "eng@example.com"
        assert audit_event.result == "success"
        assert audit_event.provider == "google"
        assert audit_event.user_email == "alice@example.com"

    def test_handle_group_member_removed_failure(self):
        """Convert failed group member removed event."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.removed",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "provider": "google",
                "success": False,
                "error_type": "transient",
                "error_message": "Temporary API error",
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]
        assert audit_event.result == "failure"
        assert audit_event.error_type == "transient"
        assert audit_event.error_message == "Temporary API error"

    def test_handle_incident_created(self):
        """Convert incident created event."""
        correlation_id = uuid4()
        event = Event(
            event_type="incident.created",
            correlation_id=correlation_id,
            user_email="oncall@example.com",
            metadata={
                "incident_id": "INC-12345",
                "provider": "opsgenie",
                "success": True,
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]
        assert audit_event.action == "incident_created"
        assert audit_event.resource_type == "incident"
        assert audit_event.resource_id == "INC-12345"

    def test_handle_event_with_empty_user_email(self):
        """Use 'system' as user_email if event has empty user_email."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="",
            metadata={
                "group_id": "eng@example.com",
                "provider": "google",
                "success": True,
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]
        assert audit_event.user_email == "system"

    def test_handle_event_with_missing_resource_info(self):
        """Use 'unknown' for missing resource type/id."""
        correlation_id = uuid4()
        event = Event(
            event_type="unknown.action",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={"success": True},
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]
        assert audit_event.resource_type == "unknown"
        assert audit_event.resource_id == "unknown"


@pytest.mark.unit
class TestAuditHandlerMetadataFiltering:
    """Tests for metadata filtering in audit events."""

    def test_filter_structural_metadata(self):
        """Remove structural fields from metadata before creating audit event."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "provider": "google",
                "success": True,
                "error_type": "should_be_filtered",
                "error_message": "should_be_filtered",
                "resource_type": "should_be_filtered",
                "resource_id": "should_be_filtered",
                "result": "should_be_filtered",
                "custom_field": "should_remain",
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]
        # Verify structural fields are filtered from payload
        payload = audit_event.to_sentinel_payload()
        # custom_field should be flattened with audit_meta_ prefix
        assert "audit_meta_custom_field" in payload
        assert payload.get("audit_meta_custom_field") == "should_remain"

    def test_empty_metadata_creates_none_metadata(self):
        """Create audit event with None metadata when all fields are structural."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]
        payload = audit_event.to_sentinel_payload()
        # Should not have any audit_meta_* fields since all were filtered (group_id is resource extraction)
        audit_meta_keys = [k for k in payload.keys() if k.startswith("audit_meta_")]
        assert len(audit_meta_keys) == 0


@pytest.mark.unit
class TestAuditHandlerExceptionHandling:
    """Tests for exception handling - handler never fails."""

    def test_handler_catches_sentinel_exception(self):
        """Handler catches and logs Sentinel exceptions without re-raising."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        mock_sentinel.log_audit_event.side_effect = Exception("Sentinel error")
        handler.sentinel_client = mock_sentinel

        # Should not raise - just log
        handler.handle(event)

    def test_handler_catches_metadata_extraction_exception(self):
        """Handler catches exceptions during metadata extraction."""
        event = Event(
            event_type="group.member.added",
            correlation_id=uuid4(),
            user_email="alice@example.com",
            metadata=None,  # Will cause issues if not handled
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        # Should not raise
        handler.handle(event)

    def test_handler_function_never_raises(self):
        """Standalone handler_audit_event function never raises."""
        event = Event(
            event_type="group.member.added",
            correlation_id=uuid4(),
            user_email="alice@example.com",
            metadata={"group_id": "eng@example.com", "success": True},
        )

        # Should not raise
        handle_audit_event(event)


@pytest.mark.unit
class TestAuditHandlerWithMockedSentinel:
    """Tests with mocked Sentinel integration."""

    def test_handler_calls_log_audit_event(self):
        """Handler calls log_audit_event on Sentinel client."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "provider": "google",
                "success": True,
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        # Verify log_audit_event was called exactly once
        assert mock_sentinel.log_audit_event.call_count == 1
        # Verify an AuditEvent was passed
        call_args = mock_sentinel.log_audit_event.call_args[0]
        assert isinstance(call_args[0], AuditEvent)

    def test_handler_uses_override_sentinel_client(self):
        """Handler can use injected Sentinel client override."""
        event = Event(
            event_type="group.member.added",
            correlation_id=uuid4(),
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
            },
        )

        mock_sentinel = Mock()
        handler = AuditHandler(sentinel_client_override=mock_sentinel)

        handler.handle(event)

        assert mock_sentinel.log_audit_event.called

    def test_correlation_id_preserved(self):
        """Correlation ID from event is preserved in audit event."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]
        assert audit_event.correlation_id == str(correlation_id)

    def test_timestamp_preserved(self):
        """Event timestamp is converted to ISO format in audit event."""
        now = datetime.now()
        event = Event(
            event_type="group.member.added",
            timestamp=now,
            correlation_id=uuid4(),
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]
        # Timestamp should be ISO format string
        assert isinstance(audit_event.timestamp, str)
        assert "T" in audit_event.timestamp


@pytest.mark.unit
class TestExtractJustification:
    """Tests for justification extraction from event metadata."""

    def test_extract_justification_from_direct_metadata(self):
        """Extract justification directly from metadata."""
        metadata = {"justification": "User onboarding for project"}
        justification = _extract_justification(metadata)
        assert justification == "User onboarding for project"

    def test_extract_justification_from_request(self):
        """Extract justification from nested request object."""
        metadata = {
            "request": {
                "justification": "Team member joining for Q4 project",
                "member_email": "bob@example.com",
            }
        }
        justification = _extract_justification(metadata)
        assert justification == "Team member joining for Q4 project"

    def test_extract_justification_from_orchestration(self):
        """Extract justification from orchestration result."""
        metadata = {
            "orchestration": {
                "justification": "Access required for incident response",
                "success": True,
            }
        }
        justification = _extract_justification(metadata)
        assert justification == "Access required for incident response"

    def test_extract_justification_precedence(self):
        """Direct metadata takes precedence over nested."""
        metadata = {
            "justification": "Direct justification",
            "request": {"justification": "Request justification"},
            "orchestration": {"justification": "Orchestration justification"},
        }
        justification = _extract_justification(metadata)
        assert justification == "Direct justification"

    def test_extract_justification_request_over_orchestration(self):
        """Request takes precedence over orchestration."""
        metadata = {
            "request": {"justification": "Request justification"},
            "orchestration": {"justification": "Orchestration justification"},
        }
        justification = _extract_justification(metadata)
        assert justification == "Request justification"

    def test_extract_justification_missing_returns_none(self):
        """Return None when justification not in metadata."""
        metadata = {"group_id": "eng@example.com", "success": True}
        justification = _extract_justification(metadata)
        assert justification is None

    def test_extract_justification_empty_string_returns_none(self):
        """Return None when justification is empty string (no justification provided)."""
        metadata = {"justification": ""}
        justification = _extract_justification(metadata)
        assert justification is None


@pytest.mark.unit
class TestAuditHandlerJustificationPersistence:
    """Tests for justification persistence in audit events."""

    def test_handle_event_with_justification_in_request(self):
        """Justification from request appears in audit metadata."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "provider": "google",
                "success": True,
                "request": {
                    "member_email": "bob@example.com",
                    "justification": "User joining engineering team for Q1 project",
                },
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]

        # Justification should appear in Sentinel payload
        payload = audit_event.to_sentinel_payload()
        assert "audit_meta_justification" in payload
        assert (
            payload["audit_meta_justification"]
            == "User joining engineering team for Q1 project"
        )

    def test_handle_event_without_justification(self):
        """Event without justification does not have justification field."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "provider": "google",
                "success": True,
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]
        payload = audit_event.to_sentinel_payload()

        # Justification should not appear if not provided
        assert "audit_meta_justification" not in payload

    def test_handle_event_with_direct_justification(self):
        """Justification directly in metadata is preserved."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.removed",
            correlation_id=correlation_id,
            user_email="manager@example.com",
            metadata={
                "group_id": "eng@example.com",
                "provider": "google",
                "success": True,
                "justification": "User offboarding - left company",
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        handler.handle(event)

        audit_event = mock_sentinel.log_audit_event.call_args[0][0]
        payload = audit_event.to_sentinel_payload()
        assert payload["audit_meta_justification"] == "User offboarding - left company"


@pytest.mark.unit
class TestAuditHandlerDynamoDBIntegration:
    """Tests for DynamoDB dual-write functionality."""

    def test_handler_writes_to_dynamodb(self):
        """Audit handler writes to both Sentinel and DynamoDB."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "provider": "google",
                "success": True,
                "request": {
                    "justification": "User onboarding",
                },
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        # Mock DynamoDB write
        with patch(
            "infrastructure.events.handlers.audit.dynamodb_audit"
        ) as mock_dynamodb:
            mock_dynamodb.write_audit_event.return_value = True

            handler.handle(event)

            # Verify both Sentinel and DynamoDB were called
            assert mock_sentinel.log_audit_event.called
            assert mock_dynamodb.write_audit_event.called

            # Verify same audit event was passed to both
            sentinel_event = mock_sentinel.log_audit_event.call_args[0][0]
            dynamodb_event = mock_dynamodb.write_audit_event.call_args[0][0]
            assert sentinel_event.correlation_id == dynamodb_event.correlation_id
            assert sentinel_event.action == dynamodb_event.action

    def test_handler_continues_if_dynamodb_fails(self):
        """Handler continues even if DynamoDB write fails."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        # Mock DynamoDB write failure
        with patch(
            "infrastructure.events.handlers.audit.dynamodb_audit"
        ) as mock_dynamodb:
            mock_dynamodb.write_audit_event.return_value = False

            # Should not raise exception
            handler.handle(event)

            # Sentinel write should still succeed
            assert mock_sentinel.log_audit_event.called

    def test_handler_resilient_to_dynamodb_exception(self):
        """Handler is resilient to DynamoDB exceptions."""
        correlation_id = uuid4()
        event = Event(
            event_type="group.member.added",
            correlation_id=correlation_id,
            user_email="alice@example.com",
            metadata={
                "group_id": "eng@example.com",
                "success": True,
            },
        )

        handler = AuditHandler()
        mock_sentinel = Mock()
        handler.sentinel_client = mock_sentinel

        # Mock DynamoDB raising exception
        with patch(
            "infrastructure.events.handlers.audit.dynamodb_audit"
        ) as mock_dynamodb:
            mock_dynamodb.write_audit_event.side_effect = Exception("DynamoDB error")

            # Should not raise exception - handler is resilient
            handler.handle(event)

            # Sentinel write should still succeed
            assert mock_sentinel.log_audit_event.called
