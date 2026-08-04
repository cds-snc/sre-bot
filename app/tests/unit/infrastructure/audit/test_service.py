"""Unit tests for AuditTrailService.

Tests write and query operations on AuditTrailService using a mocked
StorageService — no DynamoDB calls are made.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from infrastructure.audit.models import AuditEvent
from infrastructure.audit.protocol import AuditTrailService
from infrastructure.audit.service import DynamoDBAuditTrailService
from infrastructure.operations.result import OperationResult


def _make_event(**kwargs) -> AuditEvent:
    defaults = dict(
        correlation_id=str(uuid4()),
        timestamp=datetime.now(UTC).isoformat(),
        action="group_member_added",
        user_email="alice@example.com",
        result="success",
    )
    defaults.update(kwargs)
    return AuditEvent(**defaults)


def _make_service(storage: MagicMock) -> AuditTrailService:
    return DynamoDBAuditTrailService(storage=storage)


@pytest.mark.unit
class TestWriteAuditEvent:
    """Tests for AuditTrailService.write_audit_event."""

    def test_write_success_returns_true(self):
        storage = MagicMock()
        storage.put.return_value = OperationResult.success(data=None)
        service = _make_service(storage)

        result = service.write_audit_event(_make_event())

        assert result is True
        assert storage.put.called

    def test_write_calls_correct_table(self):
        storage = MagicMock()
        storage.put.return_value = OperationResult.success(data=None)
        service = _make_service(storage)

        service.write_audit_event(_make_event())

        table, item = storage.put.call_args[0]
        assert table == "sre_bot_audit_trail"

    def test_write_item_contains_required_fields(self):
        storage = MagicMock()
        storage.put.return_value = OperationResult.success(data=None)
        service = _make_service(storage)
        event = _make_event(provider="google", resource_id="eng@example.com", resource_type="group")

        service.write_audit_event(event)

        _, item = storage.put.call_args[0]
        assert item["action"] == "group_member_added"
        assert item["user_email"] == "alice@example.com"
        assert item["result"] == "success"
        assert item["provider"] == "google"
        assert "ttl_timestamp" in item
        assert isinstance(item["ttl_timestamp"], int)

    def test_write_item_with_optional_resource_fields(self):
        """Resource fields are optional and included only when provided."""
        storage = MagicMock()
        storage.put.return_value = OperationResult.success(data=None)
        service = _make_service(storage)
        event = _make_event(resource_type="group", resource_id="eng@example.com")

        service.write_audit_event(event)

        _, item = storage.put.call_args[0]
        assert item["resource_type"] == "group"
        assert item["resource_id"] == "eng@example.com"

    def test_write_sort_key_format(self):
        storage = MagicMock()
        storage.put.return_value = OperationResult.success(data=None)
        service = _make_service(storage)
        event = _make_event()

        service.write_audit_event(event)

        _, item = storage.put.call_args[0]
        assert item["timestamp_correlation_id"] == f"{event.timestamp}#{event.correlation_id}"

    def test_write_includes_justification_metadata(self):
        storage = MagicMock()
        storage.put.return_value = OperationResult.success(data=None)
        service = _make_service(storage)
        event = _make_event(audit_meta_justification="User joining team for Q1 project")

        service.write_audit_event(event)

        _, item = storage.put.call_args[0]
        assert item.get("audit_meta_justification") == "User joining team for Q1 project"

    def test_write_ttl_is_future_timestamp(self):
        storage = MagicMock()
        storage.put.return_value = OperationResult.success(data=None)
        service = _make_service(storage)

        service.write_audit_event(_make_event(), retention_days=90)

        _, item = storage.put.call_args[0]
        assert item["ttl_timestamp"] > int(datetime.now(UTC).timestamp())

    def test_write_storage_error_returns_false(self):
        storage = MagicMock()
        storage.put.return_value = OperationResult.permanent_error(
            message="Table not found", error_code="ResourceNotFoundException"
        )
        service = _make_service(storage)

        result = service.write_audit_event(_make_event())

        assert result is False

    def test_write_omits_none_optional_fields(self):
        """Optional fields with None value are not included in the item."""
        storage = MagicMock()
        storage.put.return_value = OperationResult.success(data=None)
        service = _make_service(storage)
        event = _make_event()  # no provider, error_type, etc.

        service.write_audit_event(event)

        _, item = storage.put.call_args[0]
        assert "provider" not in item
        assert "error_type" not in item
        assert "error_message" not in item


@pytest.mark.unit
class TestGetAuditTrail:
    """Tests for AuditTrailService.get_audit_trail."""

    def test_returns_items_on_success(self):
        storage = MagicMock()
        items = [
            {"resource_id": "eng@example.com", "action": "group_member_added"},
            {"resource_id": "eng@example.com", "action": "group_member_removed"},
        ]
        storage.query.return_value = OperationResult.success(data=items)
        service = _make_service(storage)

        result = service.get_audit_trail("eng@example.com")

        assert result == items

    def test_uses_resource_id_as_partition_key(self):
        storage = MagicMock()
        storage.query.return_value = OperationResult.success(data=[])
        service = _make_service(storage)

        service.get_audit_trail("eng@example.com")

        _, kwargs = storage.query.call_args[0], storage.query.call_args[1]
        # table is first positional arg
        assert storage.query.call_args[0][0] == "sre_bot_audit_trail"
        assert kwargs["expression_values"][":rid"] == "eng@example.com"

    def test_limit_is_capped_at_100(self):
        storage = MagicMock()
        storage.query.return_value = OperationResult.success(data=[])
        service = _make_service(storage)

        service.get_audit_trail("eng@example.com", limit=500)

        _, kwargs = storage.query.call_args[0], storage.query.call_args[1]
        assert kwargs["Limit"] == 100

    def test_start_time_adds_sort_key_condition(self):
        storage = MagicMock()
        storage.query.return_value = OperationResult.success(data=[])
        service = _make_service(storage)
        start = datetime(2026, 1, 1, tzinfo=UTC)

        service.get_audit_trail("eng@example.com", start_time=start)

        _, kwargs = storage.query.call_args[0], storage.query.call_args[1]
        assert ":ts" in kwargs["expression_values"]
        assert kwargs["expression_values"][":ts"] == start.isoformat()

    def test_query_error_returns_empty_list(self):
        storage = MagicMock()
        storage.query.return_value = OperationResult.permanent_error(message="Error", error_code="InternalServerError")
        service = _make_service(storage)

        result = service.get_audit_trail("eng@example.com")

        assert result == []


@pytest.mark.unit
class TestGetUserAuditTrail:
    """Tests for AuditTrailService.get_user_audit_trail."""

    def test_returns_items_on_success(self):
        storage = MagicMock()
        items = [{"user_email": "alice@example.com", "action": "group_member_added"}]
        storage.query.return_value = OperationResult.success(data=items)
        service = _make_service(storage)

        result = service.get_user_audit_trail("alice@example.com")

        assert result == items

    def test_uses_gsi1(self):
        storage = MagicMock()
        storage.query.return_value = OperationResult.success(data=[])
        service = _make_service(storage)

        service.get_user_audit_trail("alice@example.com")

        _, kwargs = storage.query.call_args[0], storage.query.call_args[1]
        assert kwargs.get("IndexName") == "user_email-timestamp-index"
        assert kwargs["expression_values"][":ue"] == "alice@example.com"

    def test_query_error_returns_empty_list(self):
        storage = MagicMock()
        storage.query.return_value = OperationResult.permanent_error(message="Error", error_code="InternalServerError")
        service = _make_service(storage)

        result = service.get_user_audit_trail("alice@example.com")

        assert result == []


@pytest.mark.unit
class TestGetByCorrelationId:
    """Tests for AuditTrailService.get_by_correlation_id."""

    def test_returns_first_item_when_found(self):
        storage = MagicMock()
        event = {"correlation_id": "req-abc", "action": "group_member_added"}
        storage.query.return_value = OperationResult.success(data=[event])
        service = _make_service(storage)

        result = service.get_by_correlation_id("req-abc")

        assert result == event

    def test_returns_none_when_not_found(self):
        storage = MagicMock()
        storage.query.return_value = OperationResult.success(data=[])
        service = _make_service(storage)

        result = service.get_by_correlation_id("nonexistent")

        assert result is None

    def test_uses_gsi2(self):
        storage = MagicMock()
        storage.query.return_value = OperationResult.success(data=[])
        service = _make_service(storage)

        service.get_by_correlation_id("req-abc")

        _, kwargs = storage.query.call_args[0], storage.query.call_args[1]
        assert kwargs.get("IndexName") == "correlation_id-index"
        assert kwargs["expression_values"][":cid"] == "req-abc"

    def test_query_error_returns_none(self):
        storage = MagicMock()
        storage.query.return_value = OperationResult.permanent_error(message="Error", error_code="InternalServerError")
        service = _make_service(storage)

        result = service.get_by_correlation_id("req-abc")

        assert result is None
