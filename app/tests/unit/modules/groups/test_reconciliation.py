"""Unit tests for groups reconciliation module.

Tests in-memory reconciliation store with retry logic, exponential backoff,
claim semantics, DLQ behavior, and thread safety.
"""

import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from modules.groups.reconciliation.store import (
    FailedPropagation,
    InMemoryReconciliationStore,
)

pytestmark = pytest.mark.unit


class TestFailedPropagationModel:
    """Test FailedPropagation data model."""

    def test_create_failed_propagation(self):
        """Can create FailedPropagation instance."""
        record = FailedPropagation(
            group_id="group-123",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )

        assert record.group_id == "group-123"
        assert record.provider == "aws"
        assert record.attempts == 0
        assert record.id is None

    def test_failed_propagation_defaults(self):
        """FailedPropagation has sensible defaults."""
        record = FailedPropagation()

        assert record.attempts == 0
        assert record.id is None
        assert record.created_at is not None
        assert record.updated_at is not None


class TestSaveAndRetrieve:
    """Test saving and retrieving reconciliation records."""

    def test_save_failed_propagation(self):
        """save_failed_propagation returns generated ID."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )

        record_id = store.save_failed_propagation(record)

        assert record_id is not None
        assert record.id == record_id
        assert isinstance(record_id, str)

    def test_save_sets_timestamps(self):
        """save_failed_propagation sets created_at and updated_at."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )

        before = datetime.now(timezone.utc)
        store.save_failed_propagation(record)
        after = datetime.now(timezone.utc)

        assert before <= record.created_at <= after
        assert before <= record.updated_at <= after

    def test_save_multiple_records(self):
        """Multiple records receive unique IDs."""
        store = InMemoryReconciliationStore()
        record_ids = []

        for i in range(5):
            record = FailedPropagation(
                group_id=f"group-{i}",
                provider="aws",
                payload_raw={"member": f"user{i}@example.com"},
                op_status="retryable_error",
            )
            record_id = store.save_failed_propagation(record)
            record_ids.append(record_id)

        # All IDs should be unique
        assert len(set(record_ids)) == 5


class TestFetchDue:
    """Test fetching records due for retry."""

    def test_fetch_due_empty_store(self):
        """fetch_due returns empty list for empty store."""
        store = InMemoryReconciliationStore()
        due = store.fetch_due()
        assert due == []

    def test_fetch_due_respects_backoff(self):
        """fetch_due only returns records past backoff delay."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Immediately, not due (60s default backoff)
        due = store.fetch_due()
        assert len(due) == 0

        # Simulate time passing
        with store._lock:
            store._store[record_id].updated_at = datetime.now(timezone.utc) - timedelta(
                seconds=61
            )

        # Now due
        due = store.fetch_due()
        assert len(due) == 1

    def test_fetch_due_limit(self):
        """fetch_due respects limit parameter."""
        store = InMemoryReconciliationStore()

        # Add 10 records, all eligible for retry
        for i in range(10):
            record = FailedPropagation(
                group_id=f"group-{i}",
                provider="aws",
                payload_raw={"member": f"user{i}@example.com"},
                op_status="retryable_error",
            )
            record_id = store.save_failed_propagation(record)
            # Make all due immediately
            with store._lock:
                store._store[record_id].updated_at = datetime.now(
                    timezone.utc
                ) - timedelta(seconds=61)

        # Fetch with limit
        due = store.fetch_due(limit=3)
        assert len(due) == 3

    def test_fetch_due_skips_claimed_records(self):
        """fetch_due skips records with active claims."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Make due
        with store._lock:
            store._store[record_id].updated_at = datetime.now(timezone.utc) - timedelta(
                seconds=61
            )

        # Claim it
        store.claim_record(record_id, "worker-1", lease_seconds=300)

        # Should not appear in fetch_due
        due = store.fetch_due()
        assert len(due) == 0

    def test_fetch_due_recovers_expired_claims(self):
        """fetch_due includes records with expired claims."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Manually expire the claim by modifying the expiry time
        store.claim_record(record_id, "worker-1", lease_seconds=1)

        # Make it due for retry too (past backoff)
        with store._lock:
            store._store[record_id].updated_at = datetime.now(timezone.utc) - timedelta(
                seconds=61
            )
            # Manually expire the claim
            store._claims[record_id]["expires_at"] = 0.0

        due = store.fetch_due()
        assert len(due) == 1


class TestExponentialBackoff:
    """Test exponential backoff calculation."""

    def test_backoff_progression(self):
        """Backoff delay doubles with each attempt, then caps at 3600s."""
        store = InMemoryReconciliationStore()

        expected = [60, 120, 240, 480, 960, 1920, 3600, 3600]
        for attempts, expected_delay in enumerate(expected):
            delay = store._calculate_retry_delay(attempts)
            assert delay == expected_delay

    def test_backoff_attempt_zero(self):
        """Backoff at attempt 0 is 60 seconds."""
        store = InMemoryReconciliationStore()
        delay = store._calculate_retry_delay(0)
        assert delay == 60

    def test_backoff_high_attempts(self):
        """Backoff caps at 3600 for high attempt counts."""
        store = InMemoryReconciliationStore()
        delay = store._calculate_retry_delay(100)
        assert delay == 3600


class TestClaimSemantics:
    """Test record claim operations."""

    def test_claim_record_success(self):
        """claim_record succeeds for unclaimed record."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        claimed = store.claim_record(record_id, "worker-1", lease_seconds=300)
        assert claimed is True

    def test_claim_record_fails_if_already_claimed(self):
        """claim_record fails if record already claimed."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # First claim succeeds
        assert store.claim_record(record_id, "worker-1", lease_seconds=300) is True

        # Second claim fails
        assert store.claim_record(record_id, "worker-2", lease_seconds=300) is False

    def test_claim_expires(self):
        """Expired claims can be reclaimed."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        with patch("modules.groups.reconciliation.store.datetime") as mock_datetime:
            # Claim at 1000
            mock_datetime.now.return_value.timestamp.return_value = 1000.0
            assert store.claim_record(record_id, "worker-1", lease_seconds=10) is True

            # Cannot reclaim at 1005 (within lease until 1010)
            mock_datetime.now.return_value.timestamp.return_value = 1005.0
            assert store.claim_record(record_id, "worker-2", lease_seconds=300) is False

            # Can reclaim at 1011 (after lease at 1010)
            mock_datetime.now.return_value.timestamp.return_value = 1011.0
            assert store.claim_record(record_id, "worker-2", lease_seconds=300) is True

    def test_claim_stores_worker_id(self):
        """Claim records worker ID."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        store.claim_record(record_id, "worker-42", lease_seconds=300)

        with store._lock:
            claim = store._claims[record_id]
            assert claim["worker"] == "worker-42"


class TestMarkSuccess:
    """Test marking records as successfully processed."""

    def test_mark_success_removes_record(self):
        """mark_success removes record from active store."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        stats_before = store.get_stats()
        assert stats_before["active_records"] == 1

        store.mark_success(record_id)

        stats_after = store.get_stats()
        assert stats_after["active_records"] == 0

    def test_mark_success_removes_claim(self):
        """mark_success also clears the claim."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        store.claim_record(record_id, "worker-1", lease_seconds=300)
        store.mark_success(record_id)

        # Record should not be in claims
        assert record_id not in store._claims


class TestMarkPermanentFailure:
    """Test moving records to dead-letter queue."""

    def test_mark_permanent_failure_moves_to_dlq(self):
        """mark_permanent_failure moves record to DLQ."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        stats_before = store.get_stats()
        assert stats_before["active_records"] == 1
        assert stats_before["dlq_records"] == 0

        store.mark_permanent_failure(record_id, "Max retries exceeded")

        stats_after = store.get_stats()
        assert stats_after["active_records"] == 0
        assert stats_after["dlq_records"] == 1

    def test_mark_permanent_failure_preserves_reason(self):
        """mark_permanent_failure stores failure reason."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        reason = "Permanent auth error"
        store.mark_permanent_failure(record_id, reason)

        dlq_entries = store.get_dlq_entries()
        assert len(dlq_entries) == 1
        assert reason in dlq_entries[0].last_error

    def test_mark_permanent_failure_sets_status(self):
        """mark_permanent_failure updates op_status."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        store.mark_permanent_failure(record_id, "Failed")

        dlq_entries = store.get_dlq_entries()
        assert dlq_entries[0].op_status == "permanent_error"


class TestIncrementAttempt:
    """Test incrementing attempt counters."""

    def test_increment_attempt_increments_counter(self):
        """increment_attempt increases attempts."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        store.increment_attempt(record_id)

        with store._lock:
            assert store._store[record_id].attempts == 1

    def test_increment_attempt_stores_error(self):
        """increment_attempt stores last_error."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        error_msg = "Connection timeout"
        store.increment_attempt(record_id, last_error=error_msg)

        with store._lock:
            assert store._store[record_id].last_error == error_msg

    def test_increment_attempt_moves_to_dlq_on_max(self):
        """increment_attempt moves to DLQ after max retries."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Increment 5 times (max is 5)
        for i in range(5):
            store.increment_attempt(record_id, last_error="Still failing")

        stats = store.get_stats()
        assert stats["active_records"] == 0
        assert stats["dlq_records"] == 1

    def test_increment_attempt_updates_timestamp(self):
        """increment_attempt updates updated_at."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        before = datetime.now(timezone.utc)
        store.increment_attempt(record_id)
        after = datetime.now(timezone.utc)

        with store._lock:
            assert before <= store._store[record_id].updated_at <= after


class TestStatistics:
    """Test statistics tracking."""

    def test_get_stats_empty_store(self):
        """get_stats returns zeros for empty store."""
        store = InMemoryReconciliationStore()
        stats = store.get_stats()

        assert stats["active_records"] == 0
        assert stats["claimed_records"] == 0
        assert stats["dlq_records"] == 0

    def test_get_stats_active_records(self):
        """get_stats counts active records."""
        store = InMemoryReconciliationStore()

        for i in range(3):
            record = FailedPropagation(
                group_id=f"group-{i}",
                provider="aws",
                payload_raw={"member": f"user{i}@example.com"},
                op_status="retryable_error",
            )
            store.save_failed_propagation(record)

        stats = store.get_stats()
        assert stats["active_records"] == 3

    def test_get_stats_claimed_records(self):
        """get_stats counts claimed records."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        store.claim_record(record_id, "worker-1", lease_seconds=300)

        stats = store.get_stats()
        assert stats["claimed_records"] == 1
        assert stats["active_records"] == 1  # Still active, just claimed

    def test_get_stats_dlq_records(self):
        """get_stats counts DLQ records."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        store.mark_permanent_failure(record_id, "Failed")

        stats = store.get_stats()
        assert stats["dlq_records"] == 1
        assert stats["active_records"] == 0

    def test_get_stats_complex_scenario(self):
        """get_stats correctly counts mixed states."""
        store = InMemoryReconciliationStore()

        # Create 5 records
        for i in range(5):
            record = FailedPropagation(
                group_id=f"group-{i}",
                provider="aws",
                payload_raw={"member": f"user{i}@example.com"},
                op_status="retryable_error",
            )
            store.save_failed_propagation(record)

        record_ids = list(store._store.keys())

        # Claim 2
        store.claim_record(record_ids[0], "worker-1", lease_seconds=300)
        store.claim_record(record_ids[1], "worker-2", lease_seconds=300)

        # Move 1 to DLQ
        store.mark_permanent_failure(record_ids[2], "Permanent")

        stats = store.get_stats()
        assert stats["active_records"] == 4  # 5 - 1 moved to DLQ
        assert stats["claimed_records"] == 2
        assert stats["dlq_records"] == 1


class TestGetDLQEntries:
    """Test DLQ retrieval."""

    def test_get_dlq_entries_empty(self):
        """get_dlq_entries returns empty list when no failures."""
        store = InMemoryReconciliationStore()
        dlq = store.get_dlq_entries()
        assert dlq == []

    def test_get_dlq_entries_returns_all_failed(self):
        """get_dlq_entries returns all DLQ entries."""
        store = InMemoryReconciliationStore()

        # Add 3 records and move to DLQ
        for i in range(3):
            record = FailedPropagation(
                group_id=f"group-{i}",
                provider="aws",
                payload_raw={"member": f"user{i}@example.com"},
                op_status="retryable_error",
            )
            record_id = store.save_failed_propagation(record)
            store.mark_permanent_failure(record_id, f"Reason {i}")

        dlq = store.get_dlq_entries()
        assert len(dlq) == 3

    def test_dlq_entries_preserve_data(self):
        """DLQ entries preserve original data."""
        store = InMemoryReconciliationStore()
        original = FailedPropagation(
            group_id="important-group",
            provider="aws",
            payload_raw={"member": "critical@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(original)
        store.mark_permanent_failure(record_id, "Fatal error")

        dlq = store.get_dlq_entries()
        dlq_entry = dlq[0]

        assert dlq_entry.group_id == "important-group"
        assert dlq_entry.provider == "aws"
        assert dlq_entry.payload_raw == {"member": "critical@example.com"}


class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_saves(self):
        """Multiple threads can save records safely."""
        store = InMemoryReconciliationStore()
        record_ids = []

        def save_records(thread_id):
            for i in range(5):
                record = FailedPropagation(
                    group_id=f"g{thread_id}-{i}",
                    provider="aws",
                    payload_raw={"member": f"u{thread_id}-{i}@example.com"},
                    op_status="retryable_error",
                )
                record_id = store.save_failed_propagation(record)
                record_ids.append(record_id)

        threads = []
        for tid in range(3):
            t = threading.Thread(target=save_records, args=(tid,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(record_ids) == 15
        assert len(set(record_ids)) == 15  # All unique

    def test_concurrent_claims_no_duplicates(self):
        """Only one worker can claim a record at a time."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="group-1",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        results = []

        def try_claim(worker_id):
            claimed = store.claim_record(record_id, worker_id, lease_seconds=300)
            results.append(claimed)

        threads = [
            threading.Thread(target=try_claim, args=(f"w{i}",)) for i in range(10)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Exactly 1 should succeed
        assert sum(results) == 1

    def test_concurrent_claim_and_process(self):
        """Records can be claimed, processed, and marked safely."""
        store = InMemoryReconciliationStore()

        for i in range(5):
            record = FailedPropagation(
                group_id=f"group-{i}",
                provider="aws",
                payload_raw={"member": f"user{i}@example.com"},
                op_status="retryable_error",
            )
            store.save_failed_propagation(record)

        successes = []

        def worker_loop(worker_id):
            for _ in range(10):
                record_ids = list(store._store.keys())
                if not record_ids:
                    break

                for record_id in record_ids:
                    if store.claim_record(record_id, worker_id, lease_seconds=60):
                        store.mark_success(record_id)
                        successes.append(1)

        threads = [
            threading.Thread(target=worker_loop, args=(f"w{i}",)) for i in range(3)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # All 5 records should be processed
        assert len(successes) == 5
        assert store.get_stats()["active_records"] == 0
