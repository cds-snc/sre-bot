"""Idempotency cache factory."""

from typing import Optional

import structlog

from infrastructure.configuration.infrastructure.idempotency import (
    IdempotencySettings,
    get_idempotency_settings,
)
from infrastructure.idempotency.cache import IdempotencyCache
from infrastructure.idempotency.dynamodb import DynamoDBCache
from infrastructure.idempotency.service import DynamoDBIdempotencyService
from infrastructure.idempotency.protocol import IdempotencyService

logger = structlog.get_logger().bind(component="idempotency.factory")

# Singleton cache instance
_cache_instance: Optional[IdempotencyCache] = None


def get_cache(idempotency_settings: IdempotencySettings) -> IdempotencyCache:
    """Get the idempotency cache singleton (DynamoDB-backed for multi-instance deployment).

    Args:
        idempotency_settings: Narrow idempotency settings slice.

    Returns:
        DynamoDBCache instance for shared cache across ECS tasks.
    """
    global _cache_instance

    if _cache_instance is not None:
        return _cache_instance

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


def get_idempotency_service() -> IdempotencyService:
    """Get application-scoped idempotency service singleton.

    Returns an IdempotencyService instance with DynamoDB-backed cache
    for distributed idempotency across ECS tasks.
    """
    return DynamoDBIdempotencyService(
        cache=DynamoDBCache(idempotency_settings=get_idempotency_settings())
    )
