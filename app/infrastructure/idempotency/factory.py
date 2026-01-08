"""Idempotency cache factory."""

from typing import TYPE_CHECKING
import structlog
from infrastructure.idempotency.cache import IdempotencyCache
from infrastructure.idempotency.dynamodb import DynamoDBCache

if TYPE_CHECKING:
    from infrastructure.configuration import Settings

logger = structlog.get_logger()

# Singleton cache instance
_cache_instance: IdempotencyCache = None


def get_cache(settings: "Settings") -> IdempotencyCache:
    """Get the idempotency cache singleton (DynamoDB-backed for multi-instance deployment).

    Args:
        settings: Settings instance (required for dependency injection).

    Returns:
        DynamoDBCache instance for shared cache across ECS tasks.
    """
    global _cache_instance

    if _cache_instance is not None:
        return _cache_instance

    _cache_instance = DynamoDBCache(settings=settings)
    logger.info("initialized_idempotency_cache", backend="dynamodb")

    return _cache_instance


def reset_cache() -> None:
    """Reset the cache singleton (for testing only).

    This function should only be used in tests to ensure a fresh cache
    instance between test runs.
    """
    global _cache_instance
    _cache_instance = None
    logger.debug("reset_cache_singleton")
