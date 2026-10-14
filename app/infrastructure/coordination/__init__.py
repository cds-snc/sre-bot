"""Infrastructure coordination primitives.

Concrete implementations of the ConditionalWriteStore contract
(contracts.coordination) for multi-instance deployments, plus the settings,
factory and lease helpers that build on it.

Instances can share a common table (sre_bot_idempotency) to prevent duplicate
operation execution when requests are retried across different ECS tasks.

Usage:

    from contracts.coordination import ClaimResult
    from infrastructure.coordination import get_conditional_write_store

    store = get_conditional_write_store()
    outcome = store.claim(idempotency_key)

    if outcome.result is ClaimResult.COMPLETED:
        return outcome.outcome

    if outcome.result is ClaimResult.IN_PROGRESS:
        raise RuntimeError("request is already being processed")

    result = execute_operation(...)
    store.complete(idempotency_key, result, outcome.claim_token)
    return result
"""

from infrastructure.coordination.dynamodb import DynamoDBConditionalWriteStore

# Factory functions available via direct import to avoid circular deps
from infrastructure.coordination.factory import (
    build_conditional_write_store,
    get_conditional_write_store,
    reset_conditional_write_store,
)
from infrastructure.coordination.in_memory import InMemoryConditionalWriteStore
from infrastructure.coordination.lease import (
    acquire_lease,
    get_lease_store,
    release_lease,
    run_if_leased,
)
from infrastructure.coordination.settings import ConditionalWriteSettings, get_conditional_write_settings

__all__ = [
    "DynamoDBConditionalWriteStore",
    "InMemoryConditionalWriteStore",
    "ConditionalWriteSettings",
    "get_conditional_write_settings",
    "build_conditional_write_store",
    "get_conditional_write_store",
    "reset_conditional_write_store",
    "acquire_lease",
    "release_lease",
    "get_lease_store",
    "run_if_leased",
]
