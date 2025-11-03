"""Comprehensive tests for reconciliation system."""

import time
import threading
from datetime import datetime, timedelta
from modules.groups.reconciliation import (
    InMemoryReconciliationStore,
    FailedPropagation,
)
from modules.groups import reconciliation_integration as ri


class TestInMemoryReconciliationStoreBasics:
    """Test basic store operations."""

    def test_save_failed_propagation(self):
        """Test saving a failed propagation record."""
        store = InMemoryReconciliationStore()
        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
            last_error="Connection timeout",
        )

        record_id = store.save_failed_propagation(record)

        assert record_id is not None
        assert record.id == record_id
        assert record.attempts == 0

    def test_fetch_due_empty_store(self):
        """Test fetching from empty store."""
        store = InMemoryReconciliationStore()
        due = store.fetch_due()
        assert due == []

    def test_fetch_due_respects_backoff(self):
        """Test that fetch_due respects backoff delays."""
        store = InMemoryReconciliationStore()

        # Save a record
        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={"action": "add_member", "member_email": "user@example.com"},
            op_status="retryable_error",
            last_error="Transient error",
        )
        record_id = store.save_failed_propagation(record)

        # First fetch should return empty (60 second backoff not elapsed)
        due = store.fetch_due()
        assert len(due) == 0, "Should not return records within backoff window"

        # Simulate time passing by directly modifying updated_at
        with store._lock:
            stored_record = store._store[record_id]
            stored_record.updated_at = datetime.utcnow() - timedelta(seconds=61)

        # Now should be due
        due = store.fetch_due()
        assert len(due) == 1

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delays: 60s, 120s, 240s, 480s, 960s, then capped."""
        store = InMemoryReconciliationStore()

        expected = [60, 120, 240, 480, 960, 1920, 3600, 3600]  # Last two capped at 3600

        for attempts, expected_delay in enumerate(expected):
            delay = store._calculate_retry_delay(attempts)
            assert (
                delay == expected_delay
            ), f"Attempt {attempts} should delay {expected_delay}s, got {delay}s"

    def test_claim_record(self):
        """Test claiming a record for processing."""
        store = InMemoryReconciliationStore()

        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Should be able to claim
        claimed = store.claim_record(record_id, "worker-1", lease_seconds=300)
        assert claimed is True

        # Cannot claim again (still claimed)
        claimed = store.claim_record(record_id, "worker-2", lease_seconds=300)
        assert claimed is False

    def test_claim_expiration(self):
        """Test that expired claims can be reclaimed."""
        store = InMemoryReconciliationStore()

        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Claim with short lease
        claimed = store.claim_record(record_id, "worker-1", lease_seconds=1)
        assert claimed is True

        # Immediately, cannot reclaim
        claimed = store.claim_record(record_id, "worker-2", lease_seconds=300)
        assert claimed is False

        # After lease expires, can reclaim
        time.sleep(1.1)
        claimed = store.claim_record(record_id, "worker-2", lease_seconds=300)
        assert claimed is True

    def test_mark_success_removes_record(self):
        """Test that mark_success removes record from store."""
        store = InMemoryReconciliationStore()

        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        assert store.get_stats()["active_records"] == 1

        store.mark_success(record_id)

        assert store.get_stats()["active_records"] == 0

    def test_mark_permanent_failure_moves_to_dlq(self):
        """Test that mark_permanent_failure moves record to DLQ."""
        store = InMemoryReconciliationStore()

        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        stats = store.get_stats()
        assert stats["active_records"] == 1
        assert stats["dlq_records"] == 0

        store.mark_permanent_failure(record_id, "Max retries exceeded")

        stats = store.get_stats()
        assert stats["active_records"] == 0
        assert stats["dlq_records"] == 1

        dlq_entries = store.get_dlq_entries()
        assert len(dlq_entries) == 1
        assert dlq_entries[0].op_status == "permanent_error"

    def test_increment_attempt_schedules_retry(self):
        """Test that increment_attempt schedules next retry."""
        store = InMemoryReconciliationStore()

        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Should have 0 attempts
        with store._lock:
            assert store._store[record_id].attempts == 0

        # Increment to 1
        store.increment_attempt(record_id, last_error="Transient error")

        with store._lock:
            assert store._store[record_id].attempts == 1
            assert store._store[record_id].last_error == "Transient error"

    def test_increment_attempt_dlq_on_max_retries(self):
        """Test that max retries moves record to DLQ."""
        store = InMemoryReconciliationStore()

        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        # Increment attempts to max (5 by default)
        for i in range(5):
            store.increment_attempt(record_id, last_error="Still failing")

        # Should be in DLQ now
        stats = store.get_stats()
        assert stats["active_records"] == 0
        assert stats["dlq_records"] == 1

        dlq_entries = store.get_dlq_entries()
        assert len(dlq_entries) == 1
        assert "Max retries (5) exceeded" in dlq_entries[0].last_error

    def test_get_stats_accuracy(self):
        """Test that stats accurately reflect store state."""
        store = InMemoryReconciliationStore()

        # Empty store
        stats = store.get_stats()
        assert stats["active_records"] == 0
        assert stats["claimed_records"] == 0
        assert stats["dlq_records"] == 0

        # Add records
        record1 = FailedPropagation(
            group_id="g1",
            provider="aws",
            payload_raw={"member": "u1@example.com"},
            op_status="retryable_error",
        )
        record2 = FailedPropagation(
            group_id="g2",
            provider="aws",
            payload_raw={"member": "u2@example.com"},
            op_status="retryable_error",
        )
        record3 = FailedPropagation(
            group_id="g3",
            provider="aws",
            payload_raw={"member": "u3@example.com"},
            op_status="retryable_error",
        )

        id1 = store.save_failed_propagation(record1)
        id2 = store.save_failed_propagation(record2)
        store.save_failed_propagation(record3)

        stats = store.get_stats()
        assert stats["active_records"] == 3

        # Claim one
        store.claim_record(id1, "worker-1", 300)
        stats = store.get_stats()
        assert stats["active_records"] == 3  # Still 3 active, but one claimed
        assert stats["claimed_records"] == 1

        # Move one to DLQ
        store.mark_permanent_failure(id2, "Permanent error")
        stats = store.get_stats()
        assert stats["active_records"] == 2
        assert stats["claimed_records"] == 1
        assert stats["dlq_records"] == 1


class TestThreadSafety:
    """Test thread safety of store operations."""

    def test_concurrent_claims_no_duplicates(self):
        """Test that concurrent claims don't result in duplicates."""
        store = InMemoryReconciliationStore()

        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={"member": "user@example.com"},
            op_status="retryable_error",
        )
        record_id = store.save_failed_propagation(record)

        results = []

        def try_claim(worker_id):
            claimed = store.claim_record(record_id, worker_id, lease_seconds=300)
            results.append(claimed)

        # Launch multiple threads trying to claim the same record
        threads = [
            threading.Thread(target=try_claim, args=(f"worker-{i}",)) for i in range(10)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Exactly one should have succeeded
        assert sum(results) == 1, f"Expected 1 successful claim, got {sum(results)}"

    def test_concurrent_saves(self):
        """Test that concurrent saves don't lose records."""
        store = InMemoryReconciliationStore()
        record_ids = []

        def save_records(count):
            for i in range(count):
                record = FailedPropagation(
                    group_id=f"g-{threading.current_thread().ident}",
                    provider="aws",
                    payload_raw={"member": f"user-{i}@example.com"},
                    op_status="retryable_error",
                )
                record_id = store.save_failed_propagation(record)
                record_ids.append(record_id)

        # Launch multiple threads saving records
        threads = [threading.Thread(target=save_records, args=(10,)) for _ in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should have all records
        stats = store.get_stats()
        assert (
            stats["active_records"] == 50
        ), f"Expected 50 records, got {stats['active_records']}"


class TestIntegration:
    """Integration tests with reconciliation_integration module."""

    def test_enqueue_failed_propagation(self):
        """Test enqueuing a failed propagation through integration module."""
        # Reset global store for clean test
        import modules.groups.reconciliation_integration as ri_module

        ri_module._reconciliation_store = None

        record_id = ri.enqueue_failed_propagation(
            correlation_id="test-123",
            provider="aws",
            group_id="test-group",
            member_email="user@example.com",
            action="add_member",
            error_message="Connection timeout",
        )

        assert record_id is not None

        # Verify record is in store
        store = ri.get_reconciliation_store()
        stats = store.get_stats()
        assert stats["active_records"] == 1

    def test_get_reconciliation_store_lazy_init(self):
        """Test that store is lazily initialized."""
        import modules.groups.reconciliation_integration as ri_module

        ri_module._reconciliation_store = None

        store1 = ri.get_reconciliation_store()
        store2 = ri.get_reconciliation_store()

        # Should be the same instance
        assert store1 is store2

    def test_is_reconciliation_enabled_default(self):
        """Test default reconciliation enabled state."""
        enabled = ri.is_reconciliation_enabled()
        # Should be enabled by default in tests
        assert isinstance(enabled, bool)

    def test_reconciliation_disabled(self, monkeypatch):
        """Test that enqueue does nothing when disabled."""

        # Mock settings to return False for reconciliation_enabled
        class MockGroups:
            reconciliation_enabled = False

        class MockSettings:
            groups = MockGroups()

        monkeypatch.setattr(
            "modules.groups.reconciliation_integration.settings", MockSettings()
        )

        record_id = ri.enqueue_failed_propagation(
            correlation_id="test-123",
            provider="aws",
            group_id="test-group",
            member_email="user@example.com",
            action="add_member",
            error_message="Connection timeout",
        )

        assert record_id is None


class TestEndToEndWorkflow:
    """End-to-end workflow tests."""

    def test_record_lifecycle(self):
        """Test complete lifecycle of a reconciliation record."""
        store = InMemoryReconciliationStore()

        # 1. Enqueue failure
        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={
                "correlation_id": "test-123",
                "member_email": "user@example.com",
                "action": "add_member",
            },
            op_status="retryable_error",
            last_error="Connection timeout",
        )
        record_id = store.save_failed_propagation(record)
        assert record_id is not None

        # 2. Record should not be immediately due (backoff)
        due = store.fetch_due()
        assert len(due) == 0

        # 3. Simulate time passing
        with store._lock:
            store._store[record_id].updated_at = datetime.utcnow() - timedelta(
                seconds=61
            )

        # 4. Record should now be due
        due = store.fetch_due()
        assert len(due) == 1

        # 5. Claim for processing
        claimed = store.claim_record(record_id, "worker-1", lease_seconds=300)
        assert claimed is True

        # 6. Simulate success
        store.mark_success(record_id)

        # 7. Record should be gone
        stats = store.get_stats()
        assert stats["active_records"] == 0

    def test_record_lifecycle_with_max_retries(self):
        """Test lifecycle with max retries and DLQ."""
        store = InMemoryReconciliationStore()

        # 1. Enqueue failure
        record = FailedPropagation(
            group_id="test-group",
            provider="aws",
            payload_raw={
                "correlation_id": "test-123",
                "member_email": "user@example.com",
                "action": "add_member",
            },
            op_status="retryable_error",
            last_error="Transient error",
        )
        record_id = store.save_failed_propagation(record)

        # 2-6. Try 5 times and fail each time
        attempt_count = 0
        while attempt_count < 5:
            # Make record due by advancing its updated_at time beyond backoff
            with store._lock:
                if record_id in store._store:
                    # Advance enough to overcome any exponential backoff
                    store._store[record_id].updated_at = datetime.utcnow() - timedelta(
                        seconds=4000
                    )

            # Fetch records due for retry
            due = store.fetch_due()
            
            # If no records due, the record is already in DLQ
            if len(due) == 0:
                break

            # Claim the record
            claimed = store.claim_record(record_id, "worker-1", lease_seconds=300)
            if not claimed:
                # Already claimed or gone, move to next iteration
                attempt_count += 1
                continue

            # Increment attempt (simulates failed retry)
            store.increment_attempt(record_id, last_error="Attempt failed")
            attempt_count += 1

        # Record should now be in DLQ after 5 increments
        stats = store.get_stats()
        assert stats["active_records"] == 0
        assert stats["dlq_records"] == 1

        dlq_entries = store.get_dlq_entries()
        assert len(dlq_entries) == 1
        assert "Max retries (5) exceeded" in dlq_entries[0].last_error
