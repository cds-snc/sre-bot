"""Infrastructure coordination primitives.

Concrete implementations of the ConditionalWriteStore contract
(contracts.coordination) for multi-instance deployments, plus the settings,
the store and lease store providers, and the host's run_if_leased.

Instances can share a common table (sre_bot_idempotency) to prevent duplicate
operation execution when requests are retried across different ECS tasks.

Usage:

    from contracts.coordination import LeaseStore, ReadFailurePolicy
    from infrastructure.coordination import build_conditional_write_store, get_lease_store

    lease_store = get_lease_store(ttl_seconds=1800)
    claim_token = lease_store.acquire("scheduler:job_name")
    if claim_token is not None:
        try:
            run_job()
        finally:
            lease_store.release("scheduler:job_name", claim_token)

    # IdempotencyStore is built the same way, with its own read-failure policy:
    # IdempotencyStore(build_conditional_write_store(...), read_failure_policy=ReadFailurePolicy.FAIL_CLOSED)
"""

from infrastructure.coordination.dynamodb import DynamoDBConditionalWriteStore

# Factory functions available via direct import to avoid circular deps
from infrastructure.coordination.factory import build_conditional_write_store, build_lease_store, get_lease_store
from infrastructure.coordination.in_memory import InMemoryConditionalWriteStore
from infrastructure.coordination.lease import run_if_leased
from infrastructure.coordination.settings import ConditionalWriteSettings, get_conditional_write_settings

__all__ = [
    "DynamoDBConditionalWriteStore",
    "InMemoryConditionalWriteStore",
    "ConditionalWriteSettings",
    "get_conditional_write_settings",
    "build_conditional_write_store",
    "build_lease_store",
    "get_lease_store",
    "run_if_leased",
]
