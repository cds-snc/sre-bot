"""Integration tests for reconciliation layer - DLQ handling and retry logic.

Tests the reconciliation system's failed propagation handling, DLQ processing,
exponential backoff, and event-driven retry mechanisms.

Each test:
- Mocks system boundaries (store backend, logging)
- Tests real reconciliation coordination logic
- Verifies retry scheduling and backoff calculation
- Captures side effects (record claiming, status updates)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from modules.groups.reconciliation import (
    InMemoryReconciliationStore,
    FailedPropagation,
)
from modules.groups import reconciliation_integration as ri


pytestmark = [
    pytest.mark.integration,
    pytest.mark.integration_reconciliation,
]


class TestReconciliationStoreBasics:
    """Test basic reconciliation store operations."""

    def test_save_failed_propagation_generates_id(self):
        """When saving failed propagation, record gets unique ID."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="test-group-123",
            provider="aws",
            payload_raw={"member_email": "user@example.com", "action": "add_member"},
            op_status="retryable_error",
            last_error="AWS service unavailable",
        )

        # Act
        record_id = store.save_failed_propagation(record)

        # Assert
        assert record_id is not None
        assert record.id == record_id
        assert record.attempts == 0
        assert record.created_at is not None
        assert record.updated_at is not None

    def test_save_failed_propagation_metadata_tracked(self):
        """Saved record preserves group_id, provider, and payload."""
        # Arrange
        store = InMemoryReconciliationStore()
        payload = {
            "correlation_id": "cid-123",
            "member_email": "user@example.com",
            "action": "add_member",
        }
        record = FailedPropagation(
            group_id="grp-123",
            provider="google",
            payload_raw=payload,
            op_status="transient_error",
            last_error="Rate limit exceeded",
        )

        # Act
        store.save_failed_propagation(record)

        # Assert
        assert record.group_id == "grp-123"
        assert record.provider == "google"
        assert record.payload_raw == payload
        assert record.op_status == "transient_error"

    def test_fetch_due_empty_store(self):
        """When store is empty, fetch_due returns empty list."""
        # Arrange
        store = InMemoryReconciliationStore()

        # Act
        due = store.fetch_due()

        # Assert
        assert isinstance(due, list)
        assert len(due) == 0

    def test_fetch_due_respects_exponential_backoff(self):
        """fetch_due respects exponential backoff - records not due until delay passes."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
            attempts=0,
        )
        record_id = store.save_failed_propagation(record)

        # Act - fetch immediately (within 60s backoff for attempt 0)
        due = store.fetch_due()

        # Assert - should not be due yet
        assert len(due) == 0

    def test_fetch_due_returns_when_backoff_elapsed(self):
        """fetch_due returns records when backoff delay has elapsed."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
            attempts=0,
        )
        record_id = store.save_failed_propagation(record)

        # Simulate time passing by modifying updated_at
        with store._lock:
            stored = store._store[record_id]
            stored.updated_at = datetime.utcnow() - timedelta(seconds=61)

        # Act
        due = store.fetch_due()

        # Assert
        assert len(due) == 1
        assert due[0].id == record_id

    def test_fetch_due_respects_claim_lease(self):
        """fetch_due skips records currently claimed by workers."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
            attempts=0,
        )
        record_id = store.save_failed_propagation(record)

        # Force record to be due
        with store._lock:
            stored = store._store[record_id]
            stored.updated_at = datetime.utcnow() - timedelta(seconds=61)

        # Claim the record
        store.claim_record(record_id, "worker-1", lease_seconds=300)

        # Act - fetch should skip claimed record
        due = store.fetch_due()

        # Assert
        assert len(due) == 0

    def test_fetch_due_returns_expired_claims(self):
        """fetch_due returns records when claim lease expires."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
            attempts=0,
        )
        record_id = store.save_failed_propagation(record)

        # Make record due
        with store._lock:
            stored = store._store[record_id]
            stored.updated_at = datetime.utcnow() - timedelta(seconds=61)

        # Claim with short lease
        store.claim_record(record_id, "worker-1", lease_seconds=1)

        # Simulate lease expiration
        with store._lock:
            claim = store._claims[record_id]
            claim["expires_at"] = (datetime.utcnow() - timedelta(seconds=1)).timestamp()

        # Act
        due = store.fetch_due()

        # Assert
        assert len(due) == 1
        assert due[0].id == record_id


class TestReconciliationBackoffCalculation:
    """Test exponential backoff calculation."""

    def test_backoff_exponential_growth(self):
        """Backoff delays grow exponentially: 60s, 120s, 240s, ..."""
        # Arrange
        store = InMemoryReconciliationStore()
        expected_delays = [60, 120, 240, 480, 960, 1920, 3600, 3600]

        # Act & Assert
        for attempt, expected in enumerate(expected_delays):
            delay = store._calculate_retry_delay(attempt)
            assert (
                delay == expected
            ), f"Attempt {attempt} should delay {expected}s, got {delay}s"

    def test_backoff_capped_at_one_hour(self):
        """Backoff delays capped at 1 hour (3600 seconds)."""
        # Arrange
        store = InMemoryReconciliationStore()

        # Act - test high attempt counts
        delay_5 = store._calculate_retry_delay(5)  # Should be 1920
        delay_10 = store._calculate_retry_delay(10)  # Should be capped at 3600

        # Assert
        assert delay_5 == 1920
        assert delay_10 == 3600


class TestReconciliationClaiming:
    """Test record claiming for worker processing."""

    def test_claim_record_succeeds_when_unclaimed(self):
        """claim_record succeeds on first claim."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Act
        claimed = store.claim_record(record_id, "worker-1", lease_seconds=300)

        # Assert
        assert claimed is True

    def test_claim_record_fails_when_already_claimed(self):
        """claim_record fails when record already claimed by another worker."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # First worker claims
        store.claim_record(record_id, "worker-1", lease_seconds=300)

        # Act - second worker tries to claim
        claimed = store.claim_record(record_id, "worker-2", lease_seconds=300)

        # Assert
        assert claimed is False

    def test_claim_record_with_lease_duration(self):
        """claim_record respects lease_seconds duration."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Act
        store.claim_record(record_id, "worker-1", lease_seconds=60)

        # Assert - verify claim stored with correct lease
        with store._lock:
            claim = store._claims[record_id]
            assert claim["worker"] == "worker-1"
            assert "expires_at" in claim


class TestReconciliationStatusUpdates:
    """Test marking records as success or permanent failure."""

    def test_mark_success_removes_record(self):
        """mark_success removes record from store."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Act
        store.mark_success(record_id)

        # Assert
        with store._lock:
            assert record_id not in store._store

    def test_mark_permanent_failure_moves_to_dlq(self):
        """mark_permanent_failure moves record to dead-letter queue."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="permanent_error",
        )
        record_id = store.save_failed_propagation(record)

        # Act
        store.mark_permanent_failure(record_id, "Permission denied")

        # Assert
        with store._lock:
            assert record_id not in store._store
            assert record_id in store._dlq
            dlq_record = store._dlq[record_id]
            assert dlq_record.last_error == "Permission denied"

    def test_increment_attempt_updates_counter(self):
        """increment_attempt increments attempts and updates error."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
            attempts=0,
        )
        record_id = store.save_failed_propagation(record)

        # Act
        store.increment_attempt(record_id, "Network timeout")

        # Assert
        with store._lock:
            stored = store._store[record_id]
            assert stored.attempts == 1
            assert stored.last_error == "Network timeout"

    def test_increment_attempt_max_attempts_reached(self):
        """When max attempts reached, record moved to DLQ."""
        # Arrange
        store = InMemoryReconciliationStore()
        store._max_attempts = 2
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # First increment: 0->1
        store.increment_attempt(record_id, "First failure")

        # Act - second increment: 1->2 (reaches max)
        store.increment_attempt(record_id, "Still failing")

        # Assert
        with store._lock:
            assert record_id not in store._store
            assert record_id in store._dlq


class TestReconciliationIntegration:
    """Test reconciliation integration functions."""

    def test_enqueue_failed_propagation_creates_record(self, monkeypatch):
        """enqueue_failed_propagation creates and stores failed propagation record."""
        # Arrange
        monkeypatch.setattr(
            "modules.groups.reconciliation_integration.is_reconciliation_enabled",
            MagicMock(return_value=True),
        )
        store = InMemoryReconciliationStore()
        monkeypatch.setattr(
            "modules.groups.reconciliation_integration.get_reconciliation_store",
            MagicMock(return_value=store),
        )

        # Act
        record_id = ri.enqueue_failed_propagation(
            correlation_id="cid-123",
            provider="aws",
            group_id="grp-123",
            member_email="user@example.com",
            action="add_member",
            error_message="AWS service unavailable",
        )

        # Assert
        assert record_id is not None
        with store._lock:
            assert record_id in store._store
            stored = store._store[record_id]
            assert stored.provider == "aws"
            assert stored.group_id == "grp-123"
            assert stored.payload_raw["member_email"] == "user@example.com"

    def test_enqueue_failed_propagation_disabled_returns_none(self, monkeypatch):
        """When reconciliation disabled, enqueue returns None."""
        # Arrange
        monkeypatch.setattr(
            "modules.groups.reconciliation_integration.is_reconciliation_enabled",
            MagicMock(return_value=False),
        )

        # Act
        record_id = ri.enqueue_failed_propagation(
            correlation_id="cid-123",
            provider="aws",
            group_id="grp-123",
            member_email="user@example.com",
            action="add_member",
            error_message="AWS service unavailable",
        )

        # Assert
        assert record_id is None

    def test_enqueue_failed_propagation_store_unavailable_returns_none(
        self, monkeypatch
    ):
        """When store unavailable, enqueue returns None."""
        # Arrange
        monkeypatch.setattr(
            "modules.groups.reconciliation_integration.is_reconciliation_enabled",
            MagicMock(return_value=True),
        )
        monkeypatch.setattr(
            "modules.groups.reconciliation_integration.get_reconciliation_store",
            MagicMock(return_value=None),
        )

        # Act
        record_id = ri.enqueue_failed_propagation(
            correlation_id="cid-123",
            provider="aws",
            group_id="grp-123",
            member_email="user@example.com",
            action="add_member",
            error_message="AWS service unavailable",
        )

        # Assert
        assert record_id is None


class TestReconciliationRetryWorkflow:
    """Test end-to-end retry workflow."""

    def test_full_retry_cycle_success(self):
        """Full cycle: enqueue → fetch → claim → process → mark success."""
        # Arrange
        store = InMemoryReconciliationStore()

        # Create initial record
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member", "member_email": "user@example.com"},
            op_status="retryable_error",
            attempts=0,
        )
        record_id = store.save_failed_propagation(record)

        # Force record to be due
        with store._lock:
            stored = store._store[record_id]
            stored.updated_at = datetime.utcnow() - timedelta(seconds=61)

        # Act - fetch due records
        due = store.fetch_due()
        assert len(due) == 1

        # Act - claim record
        claimed = store.claim_record(record_id, "worker-1", lease_seconds=300)
        assert claimed is True

        # Act - mark success
        store.mark_success(record_id)

        # Assert - record removed from store
        with store._lock:
            assert record_id not in store._store

    def test_full_retry_cycle_failure_to_dlq(self):
        """Full cycle: enqueue → max attempts → mark permanent failure → DLQ."""
        # Arrange
        store = InMemoryReconciliationStore()
        store._max_attempts = 2

        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
            attempts=0,
        )
        record_id = store.save_failed_propagation(record)

        # Act - first attempt increment
        store.increment_attempt(record_id, "Error 1")
        with store._lock:
            assert store._store[record_id].attempts == 1

        # Act - second attempt increment (reaches max)
        store.increment_attempt(record_id, "Error 2")

        # Assert - moved to DLQ
        with store._lock:
            assert record_id not in store._store
            assert record_id in store._dlq

    def test_partial_retry_then_success(self):
        """Record fails multiple times, eventually succeeds."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="retryable_error",
            attempts=0,
        )
        record_id = store.save_failed_propagation(record)

        # Act - first failure
        store.increment_attempt(record_id, "Attempt 1 failed")
        with store._lock:
            stored = store._store[record_id]
            stored.updated_at = datetime.utcnow() - timedelta(
                seconds=121
            )  # 120s backoff + 1s

        # Act - second failure
        store.increment_attempt(record_id, "Attempt 2 failed")
        with store._lock:
            stored = store._store[record_id]
            stored.updated_at = datetime.utcnow() - timedelta(
                seconds=241
            )  # 240s backoff + 1s

        # Assert - still retryable
        with store._lock:
            assert record_id in store._store
            assert store._store[record_id].attempts == 2

        # Act - eventually succeeds
        store.mark_success(record_id)

        # Assert - removed
        with store._lock:
            assert record_id not in store._store


class TestReconciliationMultipleRecords:
    """Test handling multiple records."""

    def test_fetch_due_multiple_records(self):
        """fetch_due returns multiple due records up to limit."""
        # Arrange
        store = InMemoryReconciliationStore()

        # Create 3 records
        record_ids = []
        for i in range(3):
            record = FailedPropagation(
                group_id=f"grp-{i}",
                provider="aws",
                payload_raw={"action": "add_member"},
                op_status="retryable_error",
            )
            record_id = store.save_failed_propagation(record)
            record_ids.append(record_id)

            # Make due
            with store._lock:
                stored = store._store[record_id]
                stored.updated_at = datetime.utcnow() - timedelta(seconds=61)

        # Act
        due = store.fetch_due(limit=10)

        # Assert
        assert len(due) == 3

    def test_fetch_due_respects_limit(self):
        """fetch_due returns no more than specified limit."""
        # Arrange
        store = InMemoryReconciliationStore()

        # Create 5 records
        for i in range(5):
            record = FailedPropagation(
                group_id=f"grp-{i}",
                provider="aws",
                payload_raw={"action": "add_member"},
                op_status="retryable_error",
            )
            record_id = store.save_failed_propagation(record)

            # Make due
            with store._lock:
                stored = store._store[record_id]
                stored.updated_at = datetime.utcnow() - timedelta(seconds=61)

        # Act
        due = store.fetch_due(limit=2)

        # Assert
        assert len(due) == 2

    def test_multiple_workers_claim_different_records(self):
        """Different workers can claim different records simultaneously."""
        # Arrange
        store = InMemoryReconciliationStore()

        records = []
        for i in range(2):
            record = FailedPropagation(
                group_id=f"grp-{i}",
                provider="aws",
                payload_raw={"action": "add_member"},
                op_status="retryable_error",
            )
            record_id = store.save_failed_propagation(record)
            records.append(record_id)

        # Act - worker 1 claims record 1
        claimed1 = store.claim_record(records[0], "worker-1", lease_seconds=300)
        # Act - worker 2 claims record 2
        claimed2 = store.claim_record(records[1], "worker-2", lease_seconds=300)

        # Assert
        assert claimed1 is True
        assert claimed2 is True


class TestReconciliationDLQ:
    """Test dead-letter queue operations."""

    def test_fetch_dlq_returns_failed_records(self):
        """DLQ contains permanently failed records."""
        # Arrange
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw={"action": "add_member"},
            op_status="permanent_error",
        )
        record_id = store.save_failed_propagation(record)

        # Act
        store.mark_permanent_failure(record_id, "Permission denied")
        dlq = store.get_dlq_entries()

        # Assert
        assert len(dlq) == 1
        assert dlq[0].id == record_id
        assert dlq[0].last_error == "Permission denied"

    def test_dlq_persists_error_context(self):
        """DLQ records preserve all error context."""
        # Arrange
        store = InMemoryReconciliationStore()
        original_payload = {
            "correlation_id": "cid-123",
            "member_email": "user@example.com",
            "action": "add_member",
        }
        record = FailedPropagation(
            group_id="grp-123",
            provider="aws",
            payload_raw=original_payload,
            op_status="permanent_error",
        )
        record_id = store.save_failed_propagation(record)

        # Manually set attempts to 5 to simulate prior retry attempts
        with store._lock:
            store._store[record_id].attempts = 5

        # Act
        store.mark_permanent_failure(record_id, "Max attempts exceeded")

        # Assert
        dlq = store.get_dlq_entries()
        dlq_record = dlq[0]
        assert dlq_record.group_id == "grp-123"
        assert dlq_record.provider == "aws"
        assert dlq_record.payload_raw == original_payload
        assert dlq_record.attempts == 5
        assert "Max attempts exceeded" in dlq_record.last_error
