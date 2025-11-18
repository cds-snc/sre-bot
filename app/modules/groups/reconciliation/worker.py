"""Reconciliation worker for retrying failed propagations.

This module implements batch processing of failed propagations with retry logic,
exponential backoff, and dead letter queue handling.
"""

from core.logging import get_module_logger
from modules.groups.reconciliation import integration as ri
from modules.groups.domain.models import NormalizedMember
from modules.groups.providers import get_provider

logger = get_module_logger()

# Worker ID for claiming records
_worker_id = "reconciliation-worker-1"


def _process_failed_propagation(record) -> bool:
    """Process a single failed propagation record.

    Attempts to retry the original operation (add_member or remove_member)
    against the provider.

    Args:
        record: FailedPropagation record to process

    Returns:
        True if successfully reconciled, False if still failing.
    """
    try:
        provider_name = record.provider
        action = record.payload_raw.get("action")
        group_id = record.group_id
        member_email = record.payload_raw.get("member_email")
        correlation_id = record.payload_raw.get("correlation_id")

        logger.info(
            "reconciliation_retry_attempt",
            record_id=record.id,
            provider=provider_name,
            action=action,
            attempt=record.attempts + 1,
            correlation_id=correlation_id,
        )

        # Get provider instance
        provider = get_provider(provider_name)

        # Create normalized member
        member_data = NormalizedMember(email=member_email)

        # Retry the operation
        if action == "add_member":
            result = provider.add_member(group_id, member_data)
        elif action == "remove_member":
            result = provider.remove_member(group_id, member_data)
        else:
            logger.error(
                "unknown_reconciliation_action",
                record_id=record.id,
                action=action,
            )
            return False

        # Check result
        if result.status == "success":
            logger.info(
                "reconciliation_succeeded",
                record_id=record.id,
                provider=provider_name,
                action=action,
                correlation_id=correlation_id,
            )
            return True
        elif result.status == "permanent_error":
            logger.warning(
                "reconciliation_permanent_error",
                record_id=record.id,
                provider=provider_name,
                action=action,
                error=result.error_message,
                correlation_id=correlation_id,
            )
            # Don't retry permanent errors - let increment_attempt handle DLQ
            return False
        else:
            # Retryable error
            logger.warning(
                "reconciliation_retry_failed",
                record_id=record.id,
                provider=provider_name,
                action=action,
                error=result.error_message,
                correlation_id=correlation_id,
            )
            return False

    except Exception as e:
        logger.error(
            "reconciliation_processing_error",
            record_id=record.id,
            provider=record.provider,
            action=record.payload_raw.get("action"),
            error=str(e),
        )
        return False


def process_reconciliation_batch():
    """Process a batch of reconciliation records.

    This function is called periodically by jobs/scheduled_tasks.py (every 5 minutes).
    It processes one batch of due records and returns immediately.

    The function:
    1. Fetches up to 10 records that are due for retry
    2. Attempts to claim each record (prevents duplicate processing)
    3. Retries the original failed operation
    4. Updates the record based on retry result:
       - Success: removes from queue
       - Permanent error: moves to DLQ
       - Transient error: increments attempt counter for later retry
    """
    try:
        # Check if reconciliation is enabled
        if not ri.is_reconciliation_enabled():
            logger.debug("reconciliation_disabled_skipping_iteration")
            return

        # Get store
        store = ri.get_reconciliation_store()
        if not store:
            logger.warning("reconciliation_store_unavailable")
            return

        # Fetch due records (up to 10 per batch)
        due_records = store.fetch_due(limit=10)

        if not due_records:
            # No records due
            logger.debug("reconciliation_no_records_due")
            return

        logger.info(
            "reconciliation_batch_processing",
            count=len(due_records),
            worker_id=_worker_id,
        )

        # Process each record
        for record in due_records:
            # Claim the record to prevent duplicate processing
            claimed = store.claim_record(
                record.id, worker_id=_worker_id, lease_seconds=300  # 5 minute lease
            )

            if not claimed:
                logger.debug("record_already_claimed", record_id=record.id)
                continue

            # Process the record
            success = _process_failed_propagation(record)

            if success:
                # Mark as successfully reconciled
                store.mark_success(record.id)
            else:
                # Increment attempt counter
                # (will move to DLQ if max retries exceeded)
                store.increment_attempt(record.id, last_error="Retry attempt failed")

        # Log stats after batch
        stats = store.get_stats()
        logger.info("reconciliation_stats", **stats)

    except Exception as e:
        logger.error("reconciliation_batch_error", error=str(e))
