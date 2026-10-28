"""Service registry pre-loaded with in-memory fakes for the registered contracts.

Tests that resolve services from the svcs registry use this instead of the real
host registration, so they need no AWS client and clear no provider cache: a
new registry holds new fakes.
"""

from collections.abc import Mapping

import svcs

from contracts.coordination import ConditionalWriteStore
from contracts.records import RecordStore
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from infrastructure.coordination import InMemoryConditionalWriteStore
from infrastructure.records.in_memory import InMemoryRecordStore
from server.configured_systems import StaticConfiguredSystems

FAKE_SLACK_TENANT = "T-FAKE-SLACK"


def build_fake_service_registry(*, configured_tenants: Mapping[WorkplaceSystem, str] | None = None) -> svcs.Registry:
    """Return a registry with an in-memory fake registered under each core contract.

    The configured systems are Slack only (FAKE_SLACK_TENANT) unless configured_tenants is given.
    """
    registry = svcs.Registry()
    registry.register_value(RecordStore, InMemoryRecordStore())
    registry.register_value(
        ConditionalWriteStore,
        InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300),
    )
    registry.register_value(
        ConfiguredSystems,
        StaticConfiguredSystems({WorkplaceSystem.SLACK: FAKE_SLACK_TENANT} if configured_tenants is None else configured_tenants),
    )
    return registry
