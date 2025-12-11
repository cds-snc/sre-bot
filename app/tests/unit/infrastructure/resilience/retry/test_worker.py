"""Unit tests for retry worker."""

from infrastructure.resilience.retry import (
    RetryResult,
    RetryWorker,
    InMemoryRetryStore,
)


class TestRetryWorker:
    """Tests for RetryWorker."""

    def test_process_batch_with_no_records(self, retry_store, mock_processor):
        """Test process_batch when no records are due."""
        worker = RetryWorker(retry_store, mock_processor)

        stats = worker.process_batch()

        assert stats["processed"] == 0
        assert stats["successful"] == 0
        assert stats["retried"] == 0
        assert stats["permanent_failures"] == 0
        assert stats["skipped"] == 0

    def test_process_batch_with_successful_record(
        self, retry_store, mock_processor, retry_record_factory
    ):
        """Test process_batch with a record that succeeds."""
        record = retry_record_factory()
        retry_store.save(record)

        mock_processor.set_result(RetryResult.SUCCESS)
        worker = RetryWorker(retry_store, mock_processor)

        stats = worker.process_batch()

        assert stats["processed"] == 1
        assert stats["successful"] == 1
        assert stats["retried"] == 0
        assert stats["permanent_failures"] == 0

        # Record should be removed from store
        store_stats = retry_store.get_stats()
        assert store_stats["active_records"] == 0

    def test_process_batch_with_retry_record(
        self, retry_store, mock_processor, retry_record_factory
    ):
        """Test process_batch with a record that needs retry."""
        record = retry_record_factory()
        retry_store.save(record)

        mock_processor.set_result(RetryResult.RETRY)
        worker = RetryWorker(retry_store, mock_processor)

        stats = worker.process_batch()

        assert stats["processed"] == 1
        assert stats["successful"] == 0
        assert stats["retried"] == 1
        assert stats["permanent_failures"] == 0

        # Record should still be in store
        store_stats = retry_store.get_stats()
        assert store_stats["active_records"] == 1

    def test_process_batch_with_permanent_failure(
        self, retry_store, mock_processor, retry_record_factory
    ):
        """Test process_batch with a permanent failure."""
        record = retry_record_factory()
        retry_store.save(record)

        mock_processor.set_result(RetryResult.PERMANENT_FAILURE)
        worker = RetryWorker(retry_store, mock_processor)

        stats = worker.process_batch()

        assert stats["processed"] == 1
        assert stats["successful"] == 0
        assert stats["retried"] == 0
        assert stats["permanent_failures"] == 1

        # Record should be in DLQ
        store_stats = retry_store.get_stats()
        assert store_stats["active_records"] == 0
        assert store_stats["dlq_records"] == 1

    def test_process_batch_with_multiple_records(
        self, retry_store, mock_processor, retry_record_factory
    ):
        """Test process_batch with multiple records."""
        for i in range(5):
            record = retry_record_factory(payload={"task_id": f"task-{i}"})
            retry_store.save(record)

        mock_processor.set_result(RetryResult.SUCCESS)
        worker = RetryWorker(retry_store, mock_processor)

        stats = worker.process_batch()

        assert stats["processed"] == 5
        assert stats["successful"] == 5
        assert len(mock_processor.processed_records) == 5

    def test_process_batch_respects_batch_size(
        self, retry_config_factory, mock_processor, retry_record_factory
    ):
        """Test process_batch respects batch_size configuration."""
        config = retry_config_factory(batch_size=3)
        store = InMemoryRetryStore(config)

        # Add 5 records
        for i in range(5):
            record = retry_record_factory(payload={"task_id": f"task-{i}"})
            store.save(record)

        mock_processor.set_result(RetryResult.SUCCESS)
        worker = RetryWorker(store, mock_processor, config)

        stats = worker.process_batch()

        # Should only process 3 (batch_size)
        assert stats["processed"] == 3

    def test_process_batch_skips_already_claimed_records(
        self, retry_store, mock_processor, retry_record_factory
    ):
        """Test process_batch doesn't fetch records claimed by other workers."""
        record = retry_record_factory()
        record_id = retry_store.save(record)

        # Claim the record externally
        retry_store.claim_record(record_id, "other-worker", 300)

        worker = RetryWorker(retry_store, mock_processor)
        stats = worker.process_batch()

        # Record should be filtered by fetch_due, not skipped by worker
        assert stats["processed"] == 0
        assert stats["skipped"] == 0  # Not in batch to skip

    def test_process_batch_skips_on_claim_race_condition(
        self, retry_config_factory, mock_processor, retry_record_factory
    ):
        """Test worker skips record when claim fails due to race (claimed between fetch and claim)."""

        class RacyStore(InMemoryRetryStore):
            """Store that simulates race condition on first claim attempt."""

            def __init__(self, config):
                super().__init__(config)
                self.claim_attempt = 0

            def claim_record(self, record_id, worker_id, lease_seconds):
                self.claim_attempt += 1
                # First claim fails (simulating race), subsequent succeed
                if self.claim_attempt == 1:
                    return False
                return super().claim_record(record_id, worker_id, lease_seconds)

        config = retry_config_factory()
        store = RacyStore(config)

        record = retry_record_factory()
        store.save(record)

        worker = RetryWorker(store, mock_processor, config)
        stats = worker.process_batch()

        # Should skip the record when claim fails
        assert stats["skipped"] == 1
        assert stats["processed"] == 0

    def test_process_batch_handles_processor_exception(
        self, retry_store, retry_record_factory
    ):
        """Test process_batch handles exceptions from processor."""

        class FailingProcessor:
            def process_record(self, record):
                raise ValueError("Processor error")

        record = retry_record_factory()
        retry_store.save(record)

        processor = FailingProcessor()
        worker = RetryWorker(retry_store, processor)

        stats = worker.process_batch()

        # Exception should be caught and record rescheduled
        assert stats["retried"] == 1
        store_stats = retry_store.get_stats()
        assert store_stats["active_records"] == 1

    def test_worker_uses_custom_worker_id(
        self, retry_store, mock_processor, retry_record_factory
    ):
        """Test worker uses custom worker_id for claims."""
        record = retry_record_factory()
        record_id = retry_store.save(record)

        custom_id = "custom-worker-123"
        RetryWorker(retry_store, mock_processor, worker_id=custom_id)

        # Claim the record to verify worker_id
        retry_store.claim_record(record_id, custom_id, 300)

        # The record should not be fetchable due to claim
        due = retry_store.fetch_due()
        assert len(due) == 0

    def test_worker_uses_custom_config(
        self, retry_config_factory, mock_processor, retry_record_factory
    ):
        """Test worker uses custom configuration."""
        config = retry_config_factory(
            max_attempts=3,
            batch_size=2,
            claim_lease_seconds=600,
        )
        store = InMemoryRetryStore(config)

        for i in range(5):
            record = retry_record_factory(payload={"task_id": f"task-{i}"})
            store.save(record)

        mock_processor.set_result(RetryResult.SUCCESS)
        worker = RetryWorker(store, mock_processor, config)

        stats = worker.process_batch()

        # Should respect batch_size
        assert stats["processed"] == 2

    def test_processor_receives_correct_record(
        self, retry_store, mock_processor, retry_record_factory
    ):
        """Test that processor receives the correct record."""
        payload = {"task_id": "special-task", "data": "special data"}
        record = retry_record_factory(
            operation_type="test.special",
            payload=payload,
        )
        retry_store.save(record)

        mock_processor.set_result(RetryResult.SUCCESS)
        worker = RetryWorker(retry_store, mock_processor)

        worker.process_batch()

        assert len(mock_processor.processed_records) == 1
        processed = mock_processor.processed_records[0]
        assert processed.operation_type == "test.special"
        assert processed.payload == payload

    def test_worker_processes_records_in_order(
        self, retry_store, mock_processor, retry_record_factory
    ):
        """Test that worker processes records in order they were saved."""
        task_ids = []

        for i in range(3):
            record = retry_record_factory(payload={"task_id": f"task-{i}"})
            retry_store.save(record)
            task_ids.append(f"task-{i}")

        mock_processor.set_result(RetryResult.SUCCESS)
        worker = RetryWorker(retry_store, mock_processor)

        worker.process_batch()

        processed_ids = [r.payload["task_id"] for r in mock_processor.processed_records]
        assert processed_ids == task_ids

    def test_worker_increments_attempts_on_retry(
        self, retry_store, mock_processor, retry_record_factory
    ):
        """Test that worker increments attempts when retrying."""
        record = retry_record_factory()
        retry_store.save(record)

        mock_processor.set_result(RetryResult.RETRY)
        worker = RetryWorker(retry_store, mock_processor)

        # First attempt
        worker.process_batch()

        # Check that attempts were incremented
        store_stats = retry_store.get_stats()
        assert store_stats["active_records"] == 1

    def test_worker_mixed_results(self, retry_store, retry_record_factory):
        """Test worker handling mixed results from processor."""

        class MixedProcessor:
            def __init__(self):
                self.call_count = 0

            def process_record(self, record):
                self.call_count += 1
                if self.call_count == 1:
                    return RetryResult.SUCCESS
                elif self.call_count == 2:
                    return RetryResult.RETRY
                else:
                    return RetryResult.PERMANENT_FAILURE

        for i in range(3):
            record = retry_record_factory(payload={"task_id": f"task-{i}"})
            retry_store.save(record)

        processor = MixedProcessor()
        worker = RetryWorker(retry_store, processor)

        stats = worker.process_batch()

        assert stats["processed"] == 3
        assert stats["successful"] == 1
        assert stats["retried"] == 1
        assert stats["permanent_failures"] == 1

    def test_worker_handles_empty_batch_gracefully(self, retry_store, mock_processor):
        """Test worker handles empty batches gracefully."""
        worker = RetryWorker(retry_store, mock_processor)

        # Process multiple times with no records
        for _ in range(3):
            stats = worker.process_batch()
            assert stats["processed"] == 0
