"""Generic retry worker and processor protocol.

This module provides the worker infrastructure for processing retry records.
Module-specific retry logic is implemented via the RetryProcessor protocol.
"""

from typing import Protocol

import structlog
from infrastructure.resilience.retry.config import RetryConfig
from infrastructure.resilience.retry.models import RetryRecord, RetryResult
from infrastructure.resilience.retry.store import RetryStore

logger = structlog.get_logger()


class RetryProcessor(Protocol):
    """Protocol for module-specific retry processing logic.

    Implementations handle the actual retry operation for their specific domain
    (e.g., groups member propagation, provisioning requests, etc.).

    Example:
        class GroupsRetryProcessor:
            def process_record(self, record: RetryRecord) -> RetryResult:
                # Extract groups-specific data from payload
                provider = record.payload["provider"]
                action = record.payload["action"]
                group_id = record.payload["group_id"]
                member_email = record.payload["member_email"]

                # Perform the operation
                result = perform_operation(provider, action, group_id, member_email)

                # Map to RetryResult
                if result.is_success:
                    return RetryResult.SUCCESS
                elif result.status == OperationStatus.PERMANENT_ERROR:
                    return RetryResult.PERMANENT_FAILURE
                else:
                    return RetryResult.RETRY
    """

    def process_record(self, record: RetryRecord) -> RetryResult:
        """Process a retry record.

        Args:
            record: RetryRecord to process

        Returns:
            RetryResult indicating the outcome
        """
        ...


class RetryWorker:
    """Generic worker for processing batches of retry records.

    This worker handles the mechanics of retry processing:
    - Fetching due records from the store
    - Claiming records to prevent duplicate processing
    - Delegating to a RetryProcessor for actual processing
    - Updating store based on results

    Attributes:
        store: RetryStore for persisting retry records
        processor: RetryProcessor for module-specific processing logic
        config: RetryConfig controlling batch size and claim lease
        worker_id: Identifier for this worker instance
    """

    def __init__(
        self,
        store: RetryStore,
        processor: RetryProcessor,
        config: RetryConfig | None = None,
        worker_id: str = "retry-worker-1",
    ) -> None:
        """Initialize the retry worker.

        Args:
            store: RetryStore implementation
            processor: RetryProcessor implementation for this module
            config: Optional RetryConfig. If not provided, uses defaults.
            worker_id: Identifier for this worker (for claim tracking)
        """
        self.store = store
        self.processor = processor
        self.config = config or RetryConfig()
        self.worker_id = worker_id
        self.log = logger.bind(component="retry_worker", worker_id=worker_id)

    def process_batch(self) -> dict:
        """Process a batch of retry records.

        Fetches due records, claims them, processes them, and updates the store
        based on results. This method is idempotent and safe to call repeatedly.

        Returns:
            Dictionary with processing statistics:
                - processed: Number of records processed
                - successful: Number of successful retries
                - retried: Number of records re-scheduled for retry
                - permanent_failures: Number moved to DLQ
                - skipped: Number that couldn't be claimed

        Example:
            stats = worker.process_batch()
            self.log.info("batch_complete", **stats)
        """
        # Fetch due records
        records = self.store.fetch_due(limit=self.config.batch_size)

        if not records:
            self.log.debug("retry_batch_no_records")
            return {
                "processed": 0,
                "successful": 0,
                "retried": 0,
                "permanent_failures": 0,
                "skipped": 0,
            }

        self.log.info(
            "retry_batch_start",
            worker_id=self.worker_id,
            record_count=len(records),
        )

        stats = {
            "processed": 0,
            "successful": 0,
            "retried": 0,
            "permanent_failures": 0,
            "skipped": 0,
        }

        for record in records:
            # Attempt to claim the record
            if not self.store.claim_record(
                record.id,  # type: ignore
                self.worker_id,
                self.config.claim_lease_seconds,
            ):
                self.log.debug(
                    "retry_record_skipped_claim_failed",
                    record_id=record.id,
                )
                stats["skipped"] += 1
                continue

            # Process the record
            try:
                result = self._process_record(record)
                stats["processed"] += 1

                if result == RetryResult.SUCCESS:
                    stats["successful"] += 1
                elif result == RetryResult.RETRY:
                    stats["retried"] += 1
                elif result == RetryResult.PERMANENT_FAILURE:
                    stats["permanent_failures"] += 1

            except Exception as e:
                self.log.error(
                    "retry_processing_exception",
                    record_id=record.id,
                    operation_type=record.operation_type,
                    error=str(e),
                    exc_info=True,
                )
                # Treat unhandled exceptions as retryable errors
                self.store.increment_attempt(
                    record.id, last_error=f"Unhandled exception: {str(e)}"  # type: ignore
                )
                stats["retried"] += 1

        self.log.info(
            "retry_batch_complete",
            worker_id=self.worker_id,
            **stats,
        )

        return stats

    def _process_record(self, record: RetryRecord) -> RetryResult:
        """Process a single retry record.

        Args:
            record: RetryRecord to process

        Returns:
            RetryResult indicating the outcome
        """
        self.log.info(
            "retry_record_processing",
            record_id=record.id,
            operation_type=record.operation_type,
            attempt=record.attempts + 1,
        )

        try:
            # Delegate to processor
            result = self.processor.process_record(record)

            # Update store based on result
            if result == RetryResult.SUCCESS:
                self.store.mark_success(record.id)  # type: ignore
                self.log.info(
                    "retry_record_succeeded",
                    record_id=record.id,
                    operation_type=record.operation_type,
                )

            elif result == RetryResult.PERMANENT_FAILURE:
                self.store.mark_permanent_failure(
                    record.id,  # type: ignore
                    reason="Processor returned permanent failure",
                )
                self.log.warning(
                    "retry_record_permanent_failure",
                    record_id=record.id,
                    operation_type=record.operation_type,
                )

            elif result == RetryResult.RETRY:
                self.store.increment_attempt(
                    record.id,  # type: ignore
                    last_error="Operation failed, will retry",
                )
                self.log.info(
                    "retry_record_rescheduled",
                    record_id=record.id,
                    operation_type=record.operation_type,
                    attempts=record.attempts + 1,
                )

            return result

        except Exception as e:
            self.log.error(
                "retry_processor_exception",
                record_id=record.id,
                operation_type=record.operation_type,
                error=str(e),
                exc_info=True,
            )
            # Increment attempt for unhandled exceptions
            self.store.increment_attempt(
                record.id, last_error=f"Processor exception: {str(e)}"  # type: ignore
            )
            return RetryResult.RETRY
