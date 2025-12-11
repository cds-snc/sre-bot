"""Unit tests for retry models."""

import pytest
from datetime import datetime, timezone

from infrastructure.resilience.retry.models import RetryRecord, RetryResult


class TestRetryResult:
    """Tests for RetryResult enum."""

    def test_retry_result_values(self):
        """Test RetryResult enum values."""
        assert RetryResult.SUCCESS.value == "success"
        assert RetryResult.RETRY.value == "retry"
        assert RetryResult.PERMANENT_FAILURE.value == "permanent_failure"

    def test_retry_result_membership(self):
        """Test RetryResult enum membership."""
        assert RetryResult.SUCCESS in RetryResult
        assert RetryResult.RETRY in RetryResult
        assert RetryResult.PERMANENT_FAILURE in RetryResult


class TestRetryRecord:
    """Tests for RetryRecord dataclass."""

    def test_create_retry_record_with_required_fields(self, retry_record_factory):
        """Test creating RetryRecord with required fields."""
        record = retry_record_factory(
            operation_type="test.operation",
            payload={"task_id": "123"},
        )

        assert record.operation_type == "test.operation"
        assert record.payload == {"task_id": "123"}
        assert record.id is None
        assert record.attempts == 0
        assert record.last_error is None
        assert isinstance(record.created_at, datetime)
        assert isinstance(record.updated_at, datetime)

    def test_create_retry_record_with_all_fields(self, retry_record_factory):
        """Test creating RetryRecord with all fields."""
        now = datetime.now(timezone.utc)
        record = retry_record_factory(
            operation_type="test.operation",
            payload={"task_id": "123"},
            id="record-1",
            attempts=3,
            last_error="Some error",
        )
        record.created_at = now
        record.updated_at = now
        record.next_retry_at = now

        assert record.operation_type == "test.operation"
        assert record.payload == {"task_id": "123"}
        assert record.id == "record-1"
        assert record.attempts == 3
        assert record.last_error == "Some error"
        assert record.created_at == now
        assert record.updated_at == now
        assert record.next_retry_at == now

    def test_retry_record_requires_operation_type(self):
        """Test that RetryRecord requires operation_type."""
        with pytest.raises(ValueError, match="operation_type is required"):
            RetryRecord(operation_type="", payload={"test": "data"})

    def test_retry_record_requires_dict_payload(self):
        """Test that RetryRecord requires payload to be a dict."""
        with pytest.raises(ValueError, match="payload must be a dictionary"):
            RetryRecord(
                operation_type="test.operation",
                payload="not a dict",  # type: ignore
            )

    def test_retry_record_payload_can_be_complex(self, retry_record_factory):
        """Test that payload can contain complex nested data."""
        complex_payload = {
            "group_id": "group-123",
            "provider": "google_workspace",
            "action": "add_member",
            "member_email": "user@example.com",
            "metadata": {
                "correlation_id": "abc-123",
                "tags": ["important", "urgent"],
                "retry_count": 2,
            },
        }

        record = retry_record_factory(
            operation_type="groups.member.propagation",
            payload=complex_payload,
        )

        assert record.payload == complex_payload
        assert record.payload["metadata"]["tags"] == ["important", "urgent"]

    def test_retry_record_timestamps_are_utc(self, retry_record_factory):
        """Test that timestamps are timezone-aware UTC."""
        record = retry_record_factory()

        assert record.created_at.tzinfo is not None
        assert record.updated_at.tzinfo is not None
        assert record.created_at.tzinfo == timezone.utc
        assert record.updated_at.tzinfo == timezone.utc

    def test_retry_record_immutable_after_creation(self, retry_record_factory):
        """Test that RetryRecord fields can be modified (it's a dataclass)."""
        record = retry_record_factory(attempts=0)

        # Dataclasses are mutable by default
        record.attempts = 5
        assert record.attempts == 5

    def test_retry_record_equality(self, retry_record_factory):
        """Test RetryRecord equality comparison."""
        record1 = retry_record_factory(
            operation_type="test.op",
            payload={"id": "1"},
        )
        record2 = retry_record_factory(
            operation_type="test.op",
            payload={"id": "1"},
        )

        # Different instances with same data are not equal (different timestamps)
        assert record1 != record2

        # Same instance is equal to itself
        assert record1 == record1

    def test_retry_record_with_groups_payload_example(self, retry_record_factory):
        """Test RetryRecord with example groups module payload."""
        record = retry_record_factory(
            operation_type="groups.member.propagation",
            payload={
                "group_id": "group-abc-123",
                "provider": "google_workspace",
                "action": "add_member",
                "member_email": "newuser@example.com",
                "correlation_id": "correlation-xyz-789",
            },
        )

        assert record.operation_type == "groups.member.propagation"
        assert record.payload["provider"] == "google_workspace"
        assert record.payload["action"] == "add_member"
