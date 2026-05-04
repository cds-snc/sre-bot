"""Idempotency cache factory."""

from typing import TYPE_CHECKING
import structlog
from infrastructure.idempotency.cache import IdempotencyCache
from infrastructure.idempotency.dynamodb import DynamoDBCache

if TYPE_CHECKING:
    from infrastructure.configuration.infrastructure.idempotency import (
        IdempotencySettings,
    )

logger = structlog.get_logger().bind(component="idempotency.factory")

# Singleton cache instance
_cache_instance: IdempotencyCache = None


def get_cache(idempotency_settings: "IdempotencySettings") -> IdempotencyCache:
    """Get the idempotency cache singleton (DynamoDB-backed for multi-instance deployment).

    Args:
        idempotency_settings: Narrow idempotency settings slice, or legacy full
            Settings object (extracts .idempotency sub-slice for backward compat).

    Returns:
        DynamoDBCache instance for shared cache across ECS tasks.
    """
    global _cache_instance

    if _cache_instance is not None:
        return _cache_instance

    # Backward compat: legacy callers (app/modules) may pass full Settings object.
    if hasattr(idempotency_settings, "idempotency"):
        idempotency_settings = idempotency_settings.idempotency

    _cache_instance = DynamoDBCache(idempotency_settings=idempotency_settings)
    log = logger.bind(backend="dynamodb")
    log.info("initialized_idempotency_cache")

    return _cache_instance


def reset_cache() -> None:
    """Reset the cache singleton (for testing only).

    This function should only be used in tests to ensure a fresh cache
    instance between test runs.
    """
    global _cache_instance
    _cache_instance = None
    logger.debug("reset_cache_singleton")
