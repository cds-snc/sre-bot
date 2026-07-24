"""Infrastructure idempotency cache.

Provides idempotency protection for API operations with DynamoDB backend for
multi-instance ECS deployments.

All instances share a common cache table (sre_bot_idempotency) to prevent
duplicate operations when requests are retried across different ECS tasks.

Usage:

    from infrastructure.idempotency import get_cache

    cache = get_cache()

    # Check for cached response
    cached = cache.get(idempotency_key)
    if cached:
        return cached

    # Execute operation
    response = execute_operation(...)

    # Cache the successful response
    cache.set(idempotency_key, response.dict(), ttl_seconds=3600)
"""

from infrastructure.idempotency.cache import IdempotencyCache
from infrastructure.idempotency.dynamodb import DynamoDBCache, DynamoDBIdempotencyStore

# Factory functions available via direct import to avoid circular deps
from infrastructure.idempotency.factory import (
    get_cache,
    get_idempotency_service,
    get_idempotency_store,
    reset_cache,
    reset_idempotency_store,
)
from infrastructure.idempotency.in_memory import InMemoryIdempotencyStore
from infrastructure.idempotency.protocol import (
    ClaimOutcome,
    ClaimResult,
    IdempotencyService,
    IdempotencyStore,
)
from infrastructure.idempotency.service import DynamoDBIdempotencyService
from infrastructure.idempotency.settings import IdempotencySettings, get_idempotency_settings

__all__ = [
    "IdempotencyCache",
    "DynamoDBCache",
    "DynamoDBIdempotencyStore",
    "InMemoryIdempotencyStore",
    "ClaimResult",
    "ClaimOutcome",
    "IdempotencyStore",
    "IdempotencyService",
    "DynamoDBIdempotencyService",
    "IdempotencySettings",
    "get_idempotency_settings",
    "get_cache",
    "reset_cache",
    "get_idempotency_store",
    "reset_idempotency_store",
    "get_idempotency_service",
]
