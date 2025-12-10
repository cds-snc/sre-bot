"""Unit tests for DynamoDB audit trail persistence layer.

Tests the dynamodb_audit module functions for writing and querying audit events
using mocked DynamoDB client responses.
"""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest

from infrastructure.audit.models import AuditEvent
from infrastructure.persistence import dynamodb_audit
from infrastructure.operations.result import OperationResult


@pytest.mark.unit
class TestWriteAuditEvent:
    """Tests for writing audit events to DynamoDB."""

    def test_write_audit_event_success(self):
        """Successfully write audit event to DynamoDB."""
        audit_event = AuditEvent(
            correlation_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            action="group_member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
            provider="google",
        )

        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.put_item.return_value = OperationResult.success(
                data={}, message="Item written"
            )

            result = dynamodb_audit.write_audit_event(audit_event)

            assert result is True
            assert mock_dynamo.put_item.called
            call_args = mock_dynamo.put_item.call_args[1]
            assert call_args["table_name"] == "sre_bot_audit_trail"
            assert "Item" in call_args

    def test_write_audit_event_with_justification(self):
        """Audit event with justification is written correctly."""
        audit_event = AuditEvent(
            correlation_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            action="group_member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
            provider="google",
            audit_meta_justification="User joining team for Q1 project",
        )

        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.put_item.return_value = OperationResult.success(
                data={}, message="Item written"
            )

            result = dynamodb_audit.write_audit_event(audit_event)

            assert result is True
            call_args = mock_dynamo.put_item.call_args[1]
            item = call_args["Item"]

            # Verify justification is included
            assert "audit_meta_justification" in item
            assert item["audit_meta_justification"] == {
                "S": "User joining team for Q1 project"
            }

    def test_write_audit_event_with_ttl(self):
        """Audit event includes TTL timestamp."""
        audit_event = AuditEvent(
            correlation_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            action="group_member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
        )

        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.put_item.return_value = OperationResult.success(
                data={}, message="Item written"
            )

            result = dynamodb_audit.write_audit_event(audit_event, retention_days=90)

            assert result is True
            call_args = mock_dynamo.put_item.call_args[1]
            item = call_args["Item"]

            # Verify TTL is set
            assert "ttl_timestamp" in item
            assert "N" in item["ttl_timestamp"]
            # TTL should be a future timestamp
            ttl_value = int(item["ttl_timestamp"]["N"])
            now_ts = int(datetime.now(timezone.utc).timestamp())
            assert ttl_value > now_ts

    def test_write_audit_event_failure_returns_false(self):
        """Write returns False on DynamoDB error."""
        audit_event = AuditEvent(
            correlation_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            action="group_member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
        )

        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.put_item.return_value = OperationResult.permanent_error(
                message="Table not found", error_code="ResourceNotFoundException"
            )

            result = dynamodb_audit.write_audit_event(audit_event)

            assert result is False

    def test_write_audit_event_exception_returns_false(self):
        """Write returns False and logs on unexpected exception."""
        audit_event = AuditEvent(
            correlation_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            action="group_member_added",
            resource_type="group",
            resource_id="eng@example.com",
            user_email="alice@example.com",
            result="success",
        )

        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.put_item.side_effect = Exception("Unexpected error")

            result = dynamodb_audit.write_audit_event(audit_event)

            assert result is False


@pytest.mark.unit
class TestGetAuditTrail:
    """Tests for querying audit trail by resource_id."""

    def test_get_audit_trail_success(self):
        """Successfully query audit trail for resource."""
        sample_items = [
            {
                "resource_id": {"S": "eng@example.com"},
                "timestamp_correlation_id": {"S": "2025-01-08T12:00:00Z#req-1"},
                "action": {"S": "group_member_added"},
                "user_email": {"S": "alice@example.com"},
            },
            {
                "resource_id": {"S": "eng@example.com"},
                "timestamp_correlation_id": {"S": "2025-01-08T11:00:00Z#req-2"},
                "action": {"S": "group_member_removed"},
                "user_email": {"S": "bob@example.com"},
            },
        ]

        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.query.return_value = OperationResult.success(
                data=sample_items, message="Query successful"
            )

            items = dynamodb_audit.get_audit_trail("eng@example.com", limit=10)

            assert len(items) == 2
            assert items[0]["action"]["S"] == "group_member_added"
            assert mock_dynamo.query.called
            call_args = mock_dynamo.query.call_args[1]
            assert call_args["table_name"] == "sre_bot_audit_trail"
            assert "KeyConditionExpression" in call_args

    def test_get_audit_trail_with_limit(self):
        """Query respects limit parameter."""
        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.query.return_value = OperationResult.success(
                data=[], message="Query successful"
            )

            dynamodb_audit.get_audit_trail("eng@example.com", limit=50)

            call_args = mock_dynamo.query.call_args[1]
            assert call_args["Limit"] == 50

    def test_get_audit_trail_limit_max_100(self):
        """Query limit capped at 100."""
        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.query.return_value = OperationResult.success(
                data=[], message="Query successful"
            )

            dynamodb_audit.get_audit_trail("eng@example.com", limit=200)

            call_args = mock_dynamo.query.call_args[1]
            assert call_args["Limit"] == 100

    def test_get_audit_trail_error_returns_empty_list(self):
        """Query error returns empty list without raising."""
        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.query.return_value = OperationResult.permanent_error(
                message="Query failed", error_code="InternalServerError"
            )

            items = dynamodb_audit.get_audit_trail("eng@example.com")

            assert items == []


@pytest.mark.unit
class TestGetUserAuditTrail:
    """Tests for querying audit trail by user_email."""

    def test_get_user_audit_trail_success(self):
        """Successfully query audit trail for user."""
        sample_items = [
            {
                "user_email": {"S": "alice@example.com"},
                "timestamp": {"S": "2025-01-08T12:00:00Z"},
                "action": {"S": "group_member_added"},
                "resource_id": {"S": "eng@example.com"},
            },
        ]

        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.query.return_value = OperationResult.success(
                data=sample_items, message="Query successful"
            )

            items = dynamodb_audit.get_user_audit_trail("alice@example.com", limit=10)

            assert len(items) == 1
            assert items[0]["user_email"]["S"] == "alice@example.com"
            assert mock_dynamo.query.called
            call_args = mock_dynamo.query.call_args[1]
            assert call_args["IndexName"] == "user_email-timestamp-index"

    def test_get_user_audit_trail_error_returns_empty_list(self):
        """Query error returns empty list without raising."""
        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.query.return_value = OperationResult.permanent_error(
                message="Query failed", error_code="InternalServerError"
            )

            items = dynamodb_audit.get_user_audit_trail("alice@example.com")

            assert items == []


@pytest.mark.unit
class TestGetByCorrelationId:
    """Tests for querying audit event by correlation_id."""

    def test_get_by_correlation_id_found(self):
        """Successfully find audit event by correlation ID."""
        sample_items = [
            {
                "correlation_id": {"S": "req-abc123"},
                "action": {"S": "group_member_added"},
                "resource_id": {"S": "eng@example.com"},
            },
        ]

        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.query.return_value = OperationResult.success(
                data=sample_items, message="Query successful"
            )

            item = dynamodb_audit.get_by_correlation_id("req-abc123")

            assert item is not None
            assert item["correlation_id"]["S"] == "req-abc123"
            assert mock_dynamo.query.called
            call_args = mock_dynamo.query.call_args[1]
            assert call_args["IndexName"] == "correlation_id-index"

    def test_get_by_correlation_id_not_found(self):
        """Return None when correlation ID not found."""
        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.query.return_value = OperationResult.success(
                data=[], message="Query successful"
            )

            item = dynamodb_audit.get_by_correlation_id("nonexistent")

            assert item is None

    def test_get_by_correlation_id_error_returns_none(self):
        """Query error returns None without raising."""
        with patch(
            "infrastructure.persistence.dynamodb_audit.dynamodb_next"
        ) as mock_dynamo:
            mock_dynamo.query.return_value = OperationResult.permanent_error(
                message="Query failed", error_code="InternalServerError"
            )

            item = dynamodb_audit.get_by_correlation_id("req-abc123")

            assert item is None
