"""Reconciliation store integration for failed propagations.

This module provides placeholder implementations for Phase 1. They are
intentionally lightweight and safe to import during the phased rollout.
"""

from typing import Optional
from uuid import uuid4
from core.logging import get_module_logger
from core.config import settings

logger = get_module_logger()


def get_reconciliation_store() -> Optional[object]:
    """Return configured reconciliation store instance placeholder.

    Phase 3 will replace this placeholder with a DynamoDB-backed store.
    """
    # Placeholder: real store implemented in Phase 3
    return None


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
    """Enqueue failed propagation for durable retry (placeholder).

    Currently logs an enqueue event and returns a generated record id when a
    reconciliation store is available. Returns None when reconciliation is
    disabled or store is not configured.
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

    record_id = str(uuid4())
    try:
        # Placeholder logging to indicate intended behavior
        logger.info(
            "failed_propagation_enqueued",
            correlation_id=correlation_id,
            record_id=record_id,
            provider=provider,
            group_id=group_id,
            member_email=member_email,
            action=action,
            error=error_message,
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
