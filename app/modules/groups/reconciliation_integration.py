"""Reconciliation store integration for failed propagations.

This module provides integration between service code and the reconciliation
store implementations (in-memory for Stage 1, DynamoDB for Stage 2, SQS for Stage 3).
"""

from typing import Optional
from core.logging import get_module_logger
from core.config import settings
from modules.groups.reconciliation import (
    InMemoryReconciliationStore,
    FailedPropagation,
    ReconciliationStore,
)

logger = get_module_logger()

# Global store instance (initialized at module load)
_reconciliation_store: Optional[ReconciliationStore] = None


def _initialize_store() -> Optional[ReconciliationStore]:
    """Initialize reconciliation store based on configuration."""
    backend = getattr(settings.groups, "reconciliation_backend", "memory")

    if backend == "memory":
        logger.info("initializing_memory_reconciliation_store")
        return InMemoryReconciliationStore()
    elif backend == "dynamodb":
        # Stage 2: DynamoDB implementation
        logger.warning("dynamodb_reconciliation_store_not_implemented")
        return None
    else:
        logger.error("unknown_reconciliation_backend", backend=backend)
        return None


def get_reconciliation_store() -> Optional[ReconciliationStore]:
    """Return configured reconciliation store instance.

    Uses lazy initialization to create the store on first access.
    """
    global _reconciliation_store

    if _reconciliation_store is None:
        _reconciliation_store = _initialize_store()

    return _reconciliation_store


def is_reconciliation_enabled() -> bool:
    """Return whether reconciliation is enabled via settings.

    Looks for `settings.groups.reconciliation_enabled` with a safe default.
    """
    groups_cfg = getattr(settings, "groups", None)
    if not groups_cfg:
        return False
    return getattr(groups_cfg, "reconciliation_enabled", True)


def enqueue_failed_propagation(
    correlation_id: str,
    provider: str,
    group_id: str,
    member_email: str,
    action: str,
    error_message: str,
) -> Optional[str]:
    """Enqueue failed propagation for durable retry.

    Persists the failed operation to the reconciliation store for later retry
    with exponential backoff. Returns the record ID if successfully enqueued,
    None otherwise.

    Args:
        correlation_id: Correlation ID for tracing
        provider: Provider name that failed
        group_id: Group ID for the operation
        member_email: Member email for the operation
        action: Action that failed ("add_member" or "remove_member")
        error_message: Error message from the failed operation

    Returns:
        Record ID if successfully enqueued, None if reconciliation is disabled
        or store is unavailable.
    """
    if not is_reconciliation_enabled():
        logger.debug(
            "reconciliation_disabled", correlation_id=correlation_id, provider=provider
        )
        return None

    store = get_reconciliation_store()
    if not store:
        logger.warning(
            "reconciliation_store_unavailable",
            correlation_id=correlation_id,
            provider=provider,
        )
        return None

    try:
        # Create failed propagation record
        record = FailedPropagation(
            group_id=group_id,
            provider=provider,
            payload_raw={
                "correlation_id": correlation_id,
                "member_email": member_email,
                "action": action,
            },
            op_status="retryable_error",
            last_error=error_message,
        )

        # Save to store
        record_id = store.save_failed_propagation(record)

        logger.info(
            "failed_propagation_enqueued",
            correlation_id=correlation_id,
            record_id=record_id,
            provider=provider,
            group_id=group_id,
            action=action,
        )
        return record_id

    except Exception as e:
        logger.error(
            "reconciliation_enqueue_failed",
            correlation_id=correlation_id,
            provider=provider,
            error=str(e),
        )
        return None
