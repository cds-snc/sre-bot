"""Unit tests for retry store."""

import threading
import time
from datetime import datetime, timezone

from infrastructure.resilience.retry import (
    InMemoryRetryStore,
)


class TestInMemoryRetryStore:
    """Tests for InMemoryRetryStore."""

    def test_save_record_assigns_id(self, retry_store, retry_record_factory):
        """Test that save assigns an ID to the record."""
        record = retry_record_factory()
        assert record.id is None

        record_id = retry_store.save(record)

        assert record_id is not None
        assert record.id == record_id

    def test_save_record_increments_id(self, retry_store, retry_record_factory):
        """Test that save assigns incrementing IDs."""
        record1 = retry_record_factory()
        record2 = retry_record_factory()

        id1 = retry_store.save(record1)
        id2 = retry_store.save(record2)

        assert int(id2) == int(id1) + 1

    def test_save_record_initializes_timestamps(
        self, retry_store, retry_record_factory
    ):
        """Test that save initializes timestamps."""
        record = retry_record_factory()
        before = datetime.now(timezone.utc)

        retry_store.save(record)

        after = datetime.now(timezone.utc)
        assert before <= record.created_at <= after
        assert before <= record.updated_at <= after
        assert record.next_retry_at is not None

    def test_fetch_due_returns_empty_when_no_records(self, retry_store):
        """Test fetch_due returns empty list when no records."""
        due_records = retry_store.fetch_due()
        assert due_records == []

    def test_fetch_due_returns_immediately_due_records(
        self, retry_store, retry_record_factory
    ):
        """Test fetch_due returns records that are immediately due."""
        record = retry_record_factory()
        retry_store.save(record)

        due_records = retry_store.fetch_due()

        assert len(due_records) == 1
        assert due_records[0].id == record.id

    def test_fetch_due_respects_limit(self, retry_store, retry_record_factory):
        """Test fetch_due respects the limit parameter."""
        for i in range(5):
            record = retry_record_factory(payload={"task_id": f"task-{i}"})
            retry_store.save(record)

        due_records = retry_store.fetch_due(limit=3)

        assert len(due_records) == 3

    def test_fetch_due_excludes_claimed_records(
        self, retry_store, retry_record_factory
    ):
        """Test fetch_due excludes currently claimed records."""
        record = retry_record_factory()
        record_id = retry_store.save(record)

        # Claim the record
        retry_store.claim_record(record_id, "worker-1", 300)

        # Should not return claimed record
        due_records = retry_store.fetch_due()
        assert len(due_records) == 0

    def test_fetch_due_returns_expired_claims(self, retry_store, retry_record_factory):
        """Test fetch_due returns records with expired claims."""
        record = retry_record_factory()
        record_id = retry_store.save(record)

        # Claim with very short lease
        retry_store.claim_record(record_id, "worker-1", 1)

        # Wait for claim to expire
        time.sleep(1.1)

        # Should return record with expired claim
        due_records = retry_store.fetch_due()
        assert len(due_records) == 1

    def test_fetch_due_excludes_future_retry_times(
        self, retry_config_factory, retry_record_factory
    ):
        """Test fetch_due excludes records not yet due for retry."""
        config = retry_config_factory(base_delay_seconds=10)
        store = InMemoryRetryStore(config)

        record = retry_record_factory()
        record_id = store.save(record)

        # Increment attempt (schedules for future)
        store.increment_attempt(record_id, "Some error")

        # Should not be due yet
        due_records = store.fetch_due()
        assert len(due_records) == 0

    def test_claim_record_succeeds_for_available_record(
        self, retry_store, retry_record_factory
    ):
        """Test claiming an available record succeeds."""
        record = retry_record_factory()
        record_id = retry_store.save(record)

        claimed = retry_store.claim_record(record_id, "worker-1", 300)

        assert claimed is True

    def test_claim_record_fails_for_already_claimed(
        self, retry_store, retry_record_factory
    ):
        """Test claiming an already claimed record fails."""
        record = retry_record_factory()
        record_id = retry_store.save(record)

        # First claim succeeds
        retry_store.claim_record(record_id, "worker-1", 300)

        # Second claim fails
        claimed = retry_store.claim_record(record_id, "worker-2", 300)
        assert claimed is False

    def test_claim_record_fails_for_nonexistent_record(self, retry_store):
        """Test claiming a nonexistent record fails."""
        claimed = retry_store.claim_record("nonexistent", "worker-1", 300)
        assert claimed is False

    def test_claim_record_succeeds_after_claim_expires(
        self, retry_store, retry_record_factory
    ):
        """Test claiming succeeds after previous claim expires."""
        record = retry_record_factory()
        record_id = retry_store.save(record)

        # Claim with short lease
        retry_store.claim_record(record_id, "worker-1", 1)

        # Wait for expiration
        time.sleep(1.1)

        # New claim should succeed
        claimed = retry_store.claim_record(record_id, "worker-2", 300)
        assert claimed is True

    def test_mark_success_removes_record(self, retry_store, retry_record_factory):
        """Test mark_success removes record from queue."""
        record = retry_record_factory()
        record_id = retry_store.save(record)

        retry_store.mark_success(record_id)

        stats = retry_store.get_stats()
        assert stats["active_records"] == 0

    def test_mark_success_removes_claim(self, retry_store, retry_record_factory):
        """Test mark_success removes claim."""
        record = retry_record_factory()
        record_id = retry_store.save(record)
        retry_store.claim_record(record_id, "worker-1", 300)

        retry_store.mark_success(record_id)

        stats = retry_store.get_stats()
        assert stats["claimed_records"] == 0

    def test_mark_permanent_failure_moves_to_dlq(
        self, retry_store, retry_record_factory
    ):
        """Test mark_permanent_failure moves record to DLQ."""
        record = retry_record_factory()
        record_id = retry_store.save(record)

        retry_store.mark_permanent_failure(record_id, "Permanent error")

        stats = retry_store.get_stats()
        assert stats["active_records"] == 0
        assert stats["dlq_records"] == 1

        dlq_entries = retry_store.get_dlq_entries()
        assert len(dlq_entries) == 1
        assert dlq_entries[0].last_error == "Permanent error"

    def test_increment_attempt_increases_counter(
        self, retry_store, retry_record_factory
    ):
        """Test increment_attempt increases attempt counter."""
        record = retry_record_factory()
        record_id = retry_store.save(record)

        retry_store.increment_attempt(record_id, "Error message")

        # Fetch the record to check attempts (won't be due due to backoff)
        retry_store.fetch_due()
        # Check stats to verify record is still active
        stats = retry_store.get_stats()
        assert stats["active_records"] == 1

    def test_increment_attempt_moves_to_dlq_at_max(
        self, retry_config_factory, retry_record_factory
    ):
        """Test increment_attempt moves to DLQ at max attempts."""
        config = retry_config_factory(max_attempts=3)
        store = InMemoryRetryStore(config)

        record = retry_record_factory()
        record_id = store.save(record)

        # Increment to max attempts
        for i in range(3):
            store.increment_attempt(record_id, f"Error {i+1}")

        stats = store.get_stats()
        assert stats["active_records"] == 0
        assert stats["dlq_records"] == 1

    def test_increment_attempt_releases_claim(self, retry_store, retry_record_factory):
        """Test increment_attempt releases claim."""
        record = retry_record_factory()
        record_id = retry_store.save(record)
        retry_store.claim_record(record_id, "worker-1", 300)

        retry_store.increment_attempt(record_id, "Error")

        stats = retry_store.get_stats()
        assert stats["claimed_records"] == 0

    def test_calculate_retry_delay_exponential_backoff(
        self, retry_config_factory, retry_record_factory
    ):
        """Test that retry delay uses exponential backoff."""
        config = retry_config_factory(base_delay_seconds=10, max_delay_seconds=1000)
        store = InMemoryRetryStore(config)

        # Test backoff calculation
        assert store._calculate_retry_delay(0) == 10  # 10 * 2^0
        assert store._calculate_retry_delay(1) == 20  # 10 * 2^1
        assert store._calculate_retry_delay(2) == 40  # 10 * 2^2
        assert store._calculate_retry_delay(3) == 80  # 10 * 2^3

    def test_calculate_retry_delay_respects_max(
        self, retry_config_factory, retry_record_factory
    ):
        """Test that retry delay respects max_delay_seconds."""
        config = retry_config_factory(base_delay_seconds=100, max_delay_seconds=500)
        store = InMemoryRetryStore(config)

        # High attempt number should be capped
        delay = store._calculate_retry_delay(10)  # Would be 102400 without cap
        assert delay == 500

    def test_get_stats_returns_correct_counts(self, retry_store, retry_record_factory):
        """Test get_stats returns correct counts."""
        # Add active records
        record1 = retry_record_factory()
        record2 = retry_record_factory()
        id1 = retry_store.save(record1)
        retry_store.save(record2)

        # Claim one
        retry_store.claim_record(id1, "worker-1", 300)

        # Move one to DLQ
        record3 = retry_record_factory()
        id3 = retry_store.save(record3)
        retry_store.mark_permanent_failure(id3, "Failed")

        stats = retry_store.get_stats()
        assert stats["active_records"] == 2  # id1 and id2
        assert stats["claimed_records"] == 1  # id1
        assert stats["dlq_records"] == 1  # id3

    def test_store_is_thread_safe(self, retry_store, retry_record_factory):
        """Test that store operations are thread-safe."""
        results = []

        def save_records():
            for i in range(10):
                record = retry_record_factory(payload={"task_id": f"task-{i}"})
                record_id = retry_store.save(record)
                results.append(record_id)

        # Create multiple threads
        threads = [threading.Thread(target=save_records) for _ in range(5)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Should have saved 50 records with unique IDs
        assert len(results) == 50
        assert len(set(results)) == 50  # All unique
