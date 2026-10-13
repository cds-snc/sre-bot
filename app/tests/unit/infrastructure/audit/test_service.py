"""Unit tests for AuditTrailService.

Write paths use a MagicMock RecordStore to inspect the stored item; query
paths seed the in-memory record store and assert on returned events, so
ordering, caps and index selection are checked as behaviour.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from contracts.operations.result import OperationResult
from infrastructure.audit.models import AuditEvent
from infrastructure.audit.protocol import AuditTrailService
from infrastructure.audit.service import AUDIT_TABLE, DynamoDBAuditTrailService
from infrastructure.records.in_memory import InMemoryRecordStore


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


def _make_service(storage: MagicMock | InMemoryRecordStore) -> AuditTrailService:
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
        assert table is AUDIT_TABLE

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


def _seed(store: InMemoryRecordStore, resource_id: str, user: str, timestamp: str, correlation_id: str) -> None:
    store.put(
        AUDIT_TABLE,
        {
            "resource_id": resource_id,
            "timestamp_correlation_id": f"{timestamp}#{correlation_id}",
            "timestamp": timestamp,
            "correlation_id": correlation_id,
            "user_email": user,
            "action": "group_member_added",
        },
    )


def _error_storage() -> MagicMock:
    storage = MagicMock()
    storage.query.return_value = OperationResult.permanent_error(message="Error", error_code="InternalServerError")
    return storage


@pytest.mark.unit
class TestGetAuditTrail:
    """Tests for AuditTrailService.get_audit_trail."""

    def test_returns_resource_events_newest_first(self):
        store = InMemoryRecordStore()
        _seed(store, "eng@example.com", "alice@example.com", "2026-01-01T00:00:00", "c1")
        _seed(store, "eng@example.com", "alice@example.com", "2026-01-03T00:00:00", "c3")
        _seed(store, "ops@example.com", "alice@example.com", "2026-01-02T00:00:00", "c2")

        result = _make_service(store).get_audit_trail("eng@example.com")

        assert [event["correlation_id"] for event in result] == ["c3", "c1"]

    def test_limit_is_capped_at_100(self):
        store = InMemoryRecordStore()
        for i in range(105):
            _seed(store, "eng@example.com", "alice@example.com", f"2026-01-01T00:00:{i:03d}", f"c{i}")

        result = _make_service(store).get_audit_trail("eng@example.com", limit=500)

        assert len(result) == 100

    def test_limit_returns_at_most_n_newest_events(self):
        store = InMemoryRecordStore()
        for day in (1, 2, 3):
            _seed(store, "eng@example.com", "alice@example.com", f"2026-01-0{day}T00:00:00", f"c{day}")

        result = _make_service(store).get_audit_trail("eng@example.com", limit=2)

        assert [event["correlation_id"] for event in result] == ["c3", "c2"]

    def test_start_time_returns_only_events_before_it(self):
        store = InMemoryRecordStore()
        _seed(store, "eng@example.com", "alice@example.com", "2025-12-31T00:00:00+00:00", "old")
        _seed(store, "eng@example.com", "alice@example.com", "2026-01-02T00:00:00+00:00", "new")

        result = _make_service(store).get_audit_trail("eng@example.com", start_time=datetime(2026, 1, 1, tzinfo=UTC))

        assert [event["correlation_id"] for event in result] == ["old"]

    def test_query_error_returns_empty_list(self):
        result = _make_service(_error_storage()).get_audit_trail("eng@example.com")

        assert result == []


@pytest.mark.unit
class TestGetUserAuditTrail:
    """Tests for AuditTrailService.get_user_audit_trail."""

    def test_returns_user_events_across_resources_newest_first(self):
        store = InMemoryRecordStore()
        _seed(store, "eng@example.com", "alice@example.com", "2026-01-01T00:00:00", "c1")
        _seed(store, "ops@example.com", "alice@example.com", "2026-01-03T00:00:00", "c3")
        _seed(store, "ops@example.com", "bob@example.com", "2026-01-02T00:00:00", "c2")

        result = _make_service(store).get_user_audit_trail("alice@example.com")

        assert [event["correlation_id"] for event in result] == ["c3", "c1"]

    def test_start_time_returns_only_events_before_it(self):
        store = InMemoryRecordStore()
        _seed(store, "eng@example.com", "alice@example.com", "2025-12-31T00:00:00+00:00", "old")
        _seed(store, "eng@example.com", "alice@example.com", "2026-01-02T00:00:00+00:00", "new")

        result = _make_service(store).get_user_audit_trail("alice@example.com", start_time=datetime(2026, 1, 1, tzinfo=UTC))

        assert [event["correlation_id"] for event in result] == ["old"]

    def test_query_error_returns_empty_list(self):
        result = _make_service(_error_storage()).get_user_audit_trail("alice@example.com")

        assert result == []


@pytest.mark.unit
class TestGetByCorrelationId:
    """Tests for AuditTrailService.get_by_correlation_id."""

    def test_returns_event_when_found(self):
        store = InMemoryRecordStore()
        _seed(store, "eng@example.com", "alice@example.com", "2026-01-01T00:00:00", "req-abc")
        _seed(store, "eng@example.com", "alice@example.com", "2026-01-02T00:00:00", "req-other")

        result = _make_service(store).get_by_correlation_id("req-abc")

        assert result is not None
        assert result["correlation_id"] == "req-abc"

    def test_returns_none_when_not_found(self):
        result = _make_service(InMemoryRecordStore()).get_by_correlation_id("nonexistent")

        assert result is None

    def test_query_error_returns_none(self):
        result = _make_service(_error_storage()).get_by_correlation_id("req-abc")

        assert result is None
