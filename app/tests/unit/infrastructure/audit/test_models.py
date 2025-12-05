"""Unit tests for audit event models.

Tests cover:
- AuditEvent creation and validation
- Sentinel payload conversion
- Metadata flattening
- Factory function
- Field validation
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from infrastructure.audit.models import AuditEvent, create_audit_event


@pytest.mark.unit
class TestAuditEventCreation:
    """Tests for AuditEvent model creation and validation."""

    def test_audit_event_minimal_creation(self):
        """AuditEvent can be created with required fields only."""
        event = AuditEvent(
            correlation_id="req-123",
            action="member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
        )

        assert event.correlation_id == "req-123"
        assert event.action == "member_added"
        assert event.resource_type == "group"
        assert event.result == "success"
        assert event.error_type is None
        assert event.error_message is None
        assert event.provider is None

    def test_audit_event_with_optional_fields(self, sample_audit_event):
        """AuditEvent can be created with all optional fields."""
        assert sample_audit_event.provider == "google"
        assert sample_audit_event.duration_ms == 500
        assert sample_audit_event.error_type is None

    def test_audit_event_failure_with_errors(self, sample_audit_event_failure):
        """AuditEvent can represent a failure with error details."""
        assert sample_audit_event_failure.result == "failure"
        assert sample_audit_event_failure.error_type == "transient"
        assert "rate limit" in sample_audit_event_failure.error_message

    def test_audit_event_default_timestamp(self):
        """AuditEvent generates ISO 8601 timestamp by default."""
        event = AuditEvent(
            correlation_id="req-123",
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
        )

        # Should be ISO format (RFC 3339)
        assert "T" in event.timestamp
        assert (
            "+" in event.timestamp or "Z" in event.timestamp or "-" in event.timestamp
        )

        # Should parse back to datetime
        parsed = datetime.fromisoformat(event.timestamp)
        assert isinstance(parsed, datetime)

    def test_audit_event_custom_timestamp(self):
        """AuditEvent accepts custom ISO 8601 timestamps."""
        custom_timestamp = "2025-01-08T10:30:45+00:00"
        event = AuditEvent(
            correlation_id="req-123",
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
            timestamp=custom_timestamp,
        )

        assert event.timestamp == custom_timestamp


@pytest.mark.unit
class TestAuditEventValidation:
    """Tests for AuditEvent field validation."""

    def test_result_must_be_success_or_failure(self):
        """result field must be 'success' or 'failure'."""
        with pytest.raises(ValidationError) as exc_info:
            AuditEvent(
                correlation_id="req-123",
                action="test",
                resource_type="test",
                resource_id="test-id",
                user_email="test@example.com",
                result="pending",  # Invalid!
            )

        assert "result" in str(exc_info.value).lower()

    def test_required_fields_validation(self):
        """All required fields must be provided."""
        with pytest.raises(ValidationError):
            AuditEvent(
                correlation_id="req-123",
                # Missing required fields
            )

    def test_audit_event_with_metadata_fields(self, sample_audit_event_with_metadata):
        """AuditEvent can store arbitrary metadata fields with audit_meta_ prefix."""
        assert sample_audit_event_with_metadata.audit_meta_propagation_count == "2"
        assert sample_audit_event_with_metadata.audit_meta_retry_count == "0"
        assert sample_audit_event_with_metadata.audit_meta_source == "api"

    def test_audit_event_accepts_extra_fields_with_prefix(self):
        """AuditEvent accepts extra fields (Config.extra='allow')."""
        event = AuditEvent(
            correlation_id="req-123",
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
            audit_meta_custom="custom_value",
            audit_meta_count="42",
        )

        assert event.audit_meta_custom == "custom_value"
        assert event.audit_meta_count == "42"


@pytest.mark.unit
class TestSentinelPayloadConversion:
    """Tests for Sentinel payload conversion."""

    def test_to_sentinel_payload_minimal(self):
        """to_sentinel_payload returns flat dict with required fields."""
        event = AuditEvent(
            correlation_id="req-123",
            action="test",
            resource_type="group",
            resource_id="group-id",
            user_email="user@example.com",
            result="success",
        )

        payload = event.to_sentinel_payload()

        assert isinstance(payload, dict)
        assert payload["correlation_id"] == "req-123"
        assert payload["action"] == "test"
        assert payload["resource_type"] == "group"
        assert payload["result"] == "success"

    def test_to_sentinel_payload_excludes_none(self):
        """to_sentinel_payload excludes None values."""
        event = AuditEvent(
            correlation_id="req-123",
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
            error_type=None,
            error_message=None,
            provider=None,
            duration_ms=None,
        )

        payload = event.to_sentinel_payload()

        assert "error_type" not in payload
        assert "error_message" not in payload
        assert "provider" not in payload
        assert "duration_ms" not in payload

    def test_to_sentinel_payload_includes_optional_fields(self, sample_audit_event):
        """to_sentinel_payload includes optional fields when set."""
        payload = sample_audit_event.to_sentinel_payload()

        assert payload["provider"] == "google"
        assert payload["duration_ms"] == 500

    def test_to_sentinel_payload_with_metadata(self, sample_audit_event_with_metadata):
        """to_sentinel_payload includes flattened metadata fields."""
        payload = sample_audit_event_with_metadata.to_sentinel_payload()

        assert "audit_meta_propagation_count" in payload
        assert "audit_meta_retry_count" in payload
        assert "audit_meta_source" in payload
        assert payload["audit_meta_propagation_count"] == "2"

    def test_to_sentinel_payload_flat_structure(self, sample_audit_event_failure):
        """to_sentinel_payload returns flat structure (no nesting)."""
        payload = sample_audit_event_failure.to_sentinel_payload()

        # All fields at top level
        for key, value in payload.items():
            assert not isinstance(value, dict), f"Nested dict found at {key}: {value}"
            assert not isinstance(value, list), f"List found at {key}: {value}"


@pytest.mark.unit
class TestCreateAuditEventFactory:
    """Tests for create_audit_event factory function."""

    def test_create_audit_event_minimal(self):
        """create_audit_event creates event with required parameters."""
        event = create_audit_event(
            correlation_id="req-123",
            action="test_action",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
        )

        assert isinstance(event, AuditEvent)
        assert event.correlation_id == "req-123"
        assert event.result == "success"

    def test_create_audit_event_with_all_parameters(self):
        """create_audit_event creates event with all optional parameters."""
        event = create_audit_event(
            correlation_id="req-123",
            action="member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
            provider="google",
            duration_ms=1500,
        )

        assert event.provider == "google"
        assert event.duration_ms == 1500

    def test_create_audit_event_failure_scenario(self):
        """create_audit_event creates failure event with error details."""
        event = create_audit_event(
            correlation_id="req-456",
            action="member_removed",
            resource_type="group",
            resource_id="group@example.com",
            user_email="bob@example.com",
            result="failure",
            error_type="permanent",
            error_message="User not found in directory",
        )

        assert event.result == "failure"
        assert event.error_type == "permanent"
        assert event.error_message == "User not found in directory"

    def test_create_audit_event_invalid_result(self):
        """create_audit_event raises ValueError for invalid result."""
        with pytest.raises(ValueError) as exc_info:
            create_audit_event(
                correlation_id="req-123",
                action="test",
                resource_type="test",
                resource_id="test-id",
                user_email="test@example.com",
                result="invalid",  # Invalid!
            )

        assert "success" in str(exc_info.value)
        assert "failure" in str(exc_info.value)

    def test_create_audit_event_flattens_metadata(self):
        """create_audit_event flattens metadata with audit_meta_ prefix."""
        metadata = {
            "propagation_count": 2,
            "retry_count": 1,
            "source": "api",
        }

        event = create_audit_event(
            correlation_id="req-123",
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
            metadata=metadata,
        )

        assert event.audit_meta_propagation_count == "2"
        assert event.audit_meta_retry_count == "1"
        assert event.audit_meta_source == "api"

    def test_create_audit_event_metadata_converts_to_strings(self):
        """create_audit_event converts all metadata values to strings."""
        metadata = {
            "count": 42,
            "ratio": 3.14,
            "enabled": True,
            "items": None,
        }

        event = create_audit_event(
            correlation_id="req-123",
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
            metadata=metadata,
        )

        assert event.audit_meta_count == "42"
        assert event.audit_meta_ratio == "3.14"
        assert event.audit_meta_enabled == "True"
        assert event.audit_meta_items is None

    def test_create_audit_event_empty_metadata(self):
        """create_audit_event handles empty metadata dict."""
        event = create_audit_event(
            correlation_id="req-123",
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
            metadata={},
        )

        assert isinstance(event, AuditEvent)

    def test_create_audit_event_none_metadata(self):
        """create_audit_event handles None metadata."""
        event = create_audit_event(
            correlation_id="req-123",
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
            metadata=None,
        )

        assert isinstance(event, AuditEvent)

    def test_create_audit_event_roundtrip(self):
        """create_audit_event result can be converted to Sentinel payload."""
        event = create_audit_event(
            correlation_id="req-123",
            action="member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
            provider="google",
            duration_ms=500,
            metadata={"propagation_count": 2},
        )

        payload = event.to_sentinel_payload()

        assert payload["correlation_id"] == "req-123"
        assert payload["action"] == "member_added"
        assert payload["audit_meta_propagation_count"] == "2"
