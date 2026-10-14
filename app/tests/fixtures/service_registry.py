"""Service registry pre-loaded with in-memory fakes for the registered contracts.

Tests that resolve services from the svcs registry use this instead of the real
host registration, so they need no AWS client and clear no provider cache: a
new registry holds new fakes.
"""

import svcs

from contracts.coordination import ConditionalWriteStore
from contracts.records import RecordStore
from infrastructure.coordination import ConditionalWriteSettings, InMemoryConditionalWriteStore
from infrastructure.records.in_memory import InMemoryRecordStore


def build_fake_service_registry() -> svcs.Registry:
    """Return a registry with an in-memory fake registered under each core contract."""
    registry = svcs.Registry()
    registry.register_value(RecordStore, InMemoryRecordStore())
    registry.register_value(
        ConditionalWriteStore,
        InMemoryConditionalWriteStore(
            settings=ConditionalWriteSettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300)
        ),
    )
    return registry
