"""Unit tests for the service_registry test fixture.

The fixture builds a fresh svcs registry with the in-memory fakes under the core
contract keys, so a test resolves services without AWS clients and without
clearing any provider cache. Two tests write to the record store to show that
each test gets its own fakes. The configured-systems fake is Slack only unless a
test passes its own tenants to build_fake_service_registry.
"""

import pytest
import svcs

from contracts.coordination import ClaimResult, ConditionalWriteStore
from contracts.records import RecordStore
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from infrastructure.coordination import InMemoryConditionalWriteStore
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.fixtures.service_registry import build_fake_service_registry

pytestmark = pytest.mark.unit


async def test_fixture_resolves_in_memory_fakes_under_the_contract_keys(service_registry: svcs.Registry) -> None:
    async with svcs.Container(service_registry) as container:
        assert isinstance(await container.aget(RecordStore), InMemoryRecordStore)
        assert isinstance(await container.aget(ConditionalWriteStore), InMemoryConditionalWriteStore)


@pytest.mark.parametrize("attempt", [1, 2])
async def test_each_test_gets_a_fresh_conditional_write_store(service_registry: svcs.Registry, attempt: int) -> None:
    """The same key is NEW in both runs: no state leaks between tests."""
    async with svcs.Container(service_registry) as container:
        store = await container.aget(ConditionalWriteStore)

        assert store.claim("fixture:isolation").result is ClaimResult.NEW


async def test_fixture_configured_systems_default_to_slack_only(service_registry: svcs.Registry) -> None:
    async with svcs.Container(service_registry) as container:
        systems = await container.aget(ConfiguredSystems)

    assert list(systems.tenants()) == [WorkplaceSystem.SLACK]


async def test_configured_tenants_override_the_default() -> None:
    tenants = {WorkplaceSystem.SLACK: "T0123", WorkplaceSystem.GOOGLE: "C0abc"}

    async with build_fake_service_registry(configured_tenants=tenants) as registry, svcs.Container(registry) as container:
        systems = await container.aget(ConfiguredSystems)

    assert dict(systems.tenants()) == tenants
