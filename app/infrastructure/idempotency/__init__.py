"""Infrastructure idempotency primitives.

Provides the atomic claim/complete/release idempotency contract with concrete
store implementations for multi-instance deployments.

Instances can share a common table (sre_bot_idempotency) to prevent duplicate
operation execution when requests are retried across different ECS tasks.

Usage:

    from infrastructure.idempotency import ClaimResult, get_idempotency_store

    store = get_idempotency_store()
    outcome = store.claim(idempotency_key)

    if outcome.result is ClaimResult.COMPLETED:
        return outcome.outcome

    if outcome.result is ClaimResult.IN_PROGRESS:
        raise RuntimeError("request is already being processed")

    result = execute_operation(...)
    store.complete(idempotency_key, result)
    return result
"""

from infrastructure.idempotency.dynamodb import DynamoDBIdempotencyStore

# Factory functions available via direct import to avoid circular deps
from infrastructure.idempotency.factory import (
    build_idempotency_store,
    get_idempotency_store,
    reset_idempotency_store,
)
from infrastructure.idempotency.in_memory import InMemoryIdempotencyStore
from infrastructure.idempotency.lease import acquire_lease, release_lease
from infrastructure.idempotency.protocol import (
    ClaimOutcome,
    ClaimResult,
    IdempotencyStore,
)
from infrastructure.idempotency.settings import IdempotencySettings, get_idempotency_settings

__all__ = [
    "DynamoDBIdempotencyStore",
    "InMemoryIdempotencyStore",
    "ClaimResult",
    "ClaimOutcome",
    "IdempotencyStore",
    "IdempotencySettings",
    "get_idempotency_settings",
    "build_idempotency_store",
    "get_idempotency_store",
    "reset_idempotency_store",
    "acquire_lease",
    "release_lease",
]
