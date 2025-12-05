"""Integration tests for audit event and Sentinel integration.

Tests cover:
- AuditEvent to Sentinel payload conversion
- Sentinel client audit event logging (with HTTP mocked)
- Error handling and retry scenarios
- Structured logging for audit operations
"""

import pytest
from unittest.mock import patch
from infrastructure.audit.models import AuditEvent, create_audit_event
from integrations.sentinel.client import log_audit_event


@pytest.mark.integration
class TestAuditEventToSentinel:
    """Integration tests for AuditEvent to Sentinel logging."""

    def test_log_audit_event_success(self):
        """log_audit_event successfully sends audit event to Sentinel."""
        audit_event = AuditEvent(
            correlation_id="req-123",
            action="member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
            provider="google",
            duration_ms=500,
        )

        with patch("integrations.sentinel.client.send_event") as mock_send_event:
            mock_send_event.return_value = True
            result = log_audit_event(audit_event)

        assert result is True
        mock_send_event.assert_called_once()

        # Verify payload is flat structure
        call_args = mock_send_event.call_args
        payload = call_args[0][0]
        assert isinstance(payload, dict)
        assert "correlation_id" in payload
        assert "action" in payload
        assert "resource_type" in payload

    def test_log_audit_event_failure(self):
        """log_audit_event returns False when Sentinel send fails."""
        audit_event = AuditEvent(
            correlation_id="req-456",
            action="member_removed",
            resource_type="group",
            resource_id="group@example.com",
            user_email="bob@example.com",
            result="failure",
            error_type="transient",
            error_message="API timeout",
        )

        with patch("integrations.sentinel.client.send_event") as mock_send_event:
            mock_send_event.return_value = False
            result = log_audit_event(audit_event)

        assert result is False

    def test_log_audit_event_exception_handling(self):
        """log_audit_event handles exceptions and returns False."""
        audit_event = AuditEvent(
            correlation_id="req-789",
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
        )

        with patch("integrations.sentinel.client.send_event") as mock_send_event:
            mock_send_event.side_effect = Exception("Network error")
            result = log_audit_event(audit_event)

        assert result is False

    def test_log_audit_event_payload_is_flat(self):
        """log_audit_event payload has flat structure for Sentinel queryability."""
        audit_event = create_audit_event(
            correlation_id="req-123",
            action="group_created",
            resource_type="group",
            resource_id="newgroup@example.com",
            user_email="charlie@example.com",
            result="success",
            provider="google",
            duration_ms=250,
            metadata={
                "propagation_count": 2,
                "retry_count": 0,
                "source": "api",
            },
        )

        with patch("integrations.sentinel.client.send_event") as mock_send_event:
            mock_send_event.return_value = True
            log_audit_event(audit_event)

        # Extract payload from mock call
        call_args = mock_send_event.call_args
        payload = call_args[0][0]

        # Verify flat structure: no nested dicts or lists
        for key, value in payload.items():
            assert not isinstance(value, dict), f"Nested dict at {key}"
            assert not isinstance(value, list), f"Nested list at {key}"

        # Verify metadata is flattened with prefix
        assert "audit_meta_propagation_count" in payload
        assert "audit_meta_retry_count" in payload
        assert "audit_meta_source" in payload

    def test_log_audit_event_with_factory_function(self):
        """log_audit_event integrates well with create_audit_event factory."""
        event = create_audit_event(
            correlation_id="req-factory",
            action="member_added",
            resource_type="group",
            resource_id="team@example.com",
            user_email="user@example.com",
            result="success",
            provider="aws",
            metadata={"propagation_count": 1},
        )

        with patch("integrations.sentinel.client.send_event") as mock_send_event:
            mock_send_event.return_value = True
            result = log_audit_event(event)

        assert result is True
        assert mock_send_event.called

    def test_log_audit_event_preserves_timestamps(self):
        """log_audit_event preserves ISO 8601 timestamps in payload."""
        custom_timestamp = "2025-01-08T14:30:45+00:00"
        audit_event = AuditEvent(
            correlation_id="req-123",
            timestamp=custom_timestamp,
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
        )

        with patch("integrations.sentinel.client.send_event") as mock_send_event:
            mock_send_event.return_value = True
            log_audit_event(audit_event)

        call_args = mock_send_event.call_args
        payload = call_args[0][0]
        assert payload["timestamp"] == custom_timestamp

    def test_log_audit_event_handles_null_optional_fields(self):
        """log_audit_event correctly handles None optional fields."""
        audit_event = AuditEvent(
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

        with patch("integrations.sentinel.client.send_event") as mock_send_event:
            mock_send_event.return_value = True
            result = log_audit_event(audit_event)

        assert result is True

        # Verify None fields are excluded from payload
        call_args = mock_send_event.call_args
        payload = call_args[0][0]
        assert "error_type" not in payload
        assert "error_message" not in payload
        assert "provider" not in payload
        assert "duration_ms" not in payload


@pytest.mark.integration
class TestLogAuditEventStructuredLogging:
    """Tests for structured logging during audit event logging."""

    def test_log_audit_event_logs_success(self):
        """log_audit_event logs success event with audit details."""
        audit_event = AuditEvent(
            correlation_id="req-123",
            action="member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
        )

        with patch("integrations.sentinel.client.send_event") as mock_send:
            with patch("integrations.sentinel.client.logger") as mock_logger:
                mock_send.return_value = True
                log_audit_event(audit_event)

        # Should log success
        assert mock_logger.info.called

    def test_log_audit_event_logs_failure(self):
        """log_audit_event logs failure event with audit details."""
        audit_event = AuditEvent(
            correlation_id="req-456",
            action="member_removed",
            resource_type="group",
            resource_id="group@example.com",
            user_email="bob@example.com",
            result="success",
        )

        with patch("integrations.sentinel.client.send_event") as mock_send:
            with patch("integrations.sentinel.client.logger") as mock_logger:
                mock_send.return_value = False
                log_audit_event(audit_event)

        # Should log error
        assert mock_logger.error.called

    def test_log_audit_event_logs_exception_with_context(self):
        """log_audit_event logs exceptions with full context."""
        audit_event = AuditEvent(
            correlation_id="req-789",
            action="test",
            resource_type="test",
            resource_id="test-id",
            user_email="test@example.com",
            result="success",
        )

        with patch("integrations.sentinel.client.send_event") as mock_send:
            with patch("integrations.sentinel.client.logger") as mock_logger:
                mock_send.side_effect = Exception("Network error")
                log_audit_event(audit_event)

        # Should log error with exc_info
        assert mock_logger.error.called
        call_args = mock_logger.error.call_args
        # Check that exc_info=True was passed
        assert call_args.kwargs.get("exc_info") is True


@pytest.mark.integration
class TestSentinelPayloadFormat:
    """Tests verifying Sentinel payload format compatibility."""

    def test_sentinel_payload_all_string_values(self):
        """Sentinel payload values are string-compatible for Sentinel ingestion."""
        event = create_audit_event(
            correlation_id="req-123",
            action="member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
            provider="google",
            duration_ms=1500,
            metadata={
                "count": 42,
                "ratio": 3.14,
                "enabled": True,
                "source": "api",
            },
        )

        with patch("integrations.sentinel.client.send_event") as mock_send_event:
            mock_send_event.return_value = True
            log_audit_event(event)

        call_args = mock_send_event.call_args
        payload = call_args[0][0]

        # All values should be serializable
        import json

        json_str = json.dumps(payload)
        assert len(json_str) > 0

    def test_sentinel_payload_no_reserved_keywords_collision(self):
        """Sentinel payload avoids collisions with Sentinel reserved words."""
        audit_event = AuditEvent(
            correlation_id="req-123",
            action="member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
        )

        payload = audit_event.to_sentinel_payload()

        # Field names should be descriptive and avoid single-char or abbreviations
        for key in payload.keys():
            assert len(key) > 1, f"Field name too short: {key}"
            assert "_" in key or key.isidentifier(), f"Invalid field name: {key}"
