"""Behavior tests for build_incident_store, the IncidentStore builder in core/api.py.

The builder runs over InMemoryRecordStore with a local ConfiguredSystems fake
and IncidentCoreSettings built from explicit values. Items are put into the
incidents table and read back through the built store, so each test observes
the table name, the tenants given to the legacy item bridge and the store
interface the entry points receive.
"""

import inspect
from collections.abc import Mapping
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from features.incident.common.settings import IncidentCoreSettings
from features.incident.core.api import IncidentStore, build_incident_store
from features.incident.core.domain import ConversationReference
from features.incident.core.store import incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

TABLE_NAME = "incidents-under-test"
SLACK_TENANT = "T0SLACK"
GOOGLE_TENANT = "C0GOOGLE"
CHANNEL = "C0INCIDENT"
CONVERSATION = ConversationReference(system=WorkplaceSystem.SLACK, tenant=SLACK_TENANT, vendor_id=CHANNEL)


class _FakeConfiguredSystems(ConfiguredSystems):
    """Returns the very mapping it was given, so a test can change it after the build."""

    def __init__(self, tenants: dict[WorkplaceSystem, str]) -> None:
        self.mapping = tenants

    def tenants(self) -> Mapping[WorkplaceSystem, str]:
        return self.mapping


def _settings(*, table_name: str = TABLE_NAME, new_incident_system: WorkplaceSystem | None = None) -> IncidentCoreSettings:
    return IncidentCoreSettings(
        incidents_table=table_name,
        new_incident_system=new_incident_system,
    )


def _legacy_item(incident_id: str) -> dict[str, Any]:
    return {
        "id": incident_id,
        "channel_id": CHANNEL,
        "name": f"Incident {incident_id}",
        "user_id": "U0DECLARER",
        "teams": ["GC Notify"],
        "status": "Open",
        "created_at": "1760536800.0",
        "severity": "sev-2",
        "meet_url": "TBC",
    }


def _records_with(table_name: str, *items: dict[str, Any]) -> InMemoryRecordStore:
    records = InMemoryRecordStore()
    for item in items:
        assert records.put(incidents_table(table_name), item).is_success
    return records


def _slack_and_google() -> _FakeConfiguredSystems:
    return _FakeConfiguredSystems({WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT})


def test_build_returns_an_incident_store() -> None:
    store = build_incident_store(InMemoryRecordStore(), _slack_and_google(), _settings())

    assert isinstance(store, IncidentStore)


def test_build_reads_the_incidents_table_named_in_the_settings() -> None:
    """An item in the configured table is found; the same id in the default table is not."""
    records = _records_with(TABLE_NAME, _legacy_item("inc-configured"))
    assert records.put(incidents_table("incidents"), _legacy_item("inc-default")).is_success

    store = build_incident_store(records, _slack_and_google(), _settings())

    assert store.get("inc-configured").is_success
    assert store.get("inc-default").status is OperationStatus.NOT_FOUND


def test_builder_is_a_plain_function_returning_a_new_store_per_call() -> None:
    """No process-wide cache: each entry point scope builds its own store."""
    records = InMemoryRecordStore()
    systems = _slack_and_google()

    assert not hasattr(build_incident_store, "cache_clear")
    assert build_incident_store(records, systems, _settings()) is not build_incident_store(records, systems, _settings())


@pytest.mark.parametrize("new_incident_system", [None, WorkplaceSystem.SLACK, WorkplaceSystem.GOOGLE])
def test_build_ignores_the_new_incident_policy(new_incident_system: WorkplaceSystem | None) -> None:
    """Lookups of existing incidents read the same whatever the policy says."""
    records = _records_with(TABLE_NAME, _legacy_item("inc-policy"))

    store = build_incident_store(records, _slack_and_google(), _settings(new_incident_system=new_incident_system))

    found = store.find_by_conversation(CONVERSATION)
    assert found.data is not None
    assert found.data.id == "inc-policy"


def test_builder_source_never_names_the_new_incident_policy() -> None:
    assert "new_incident_system" not in inspect.getsource(build_incident_store)


def test_legacy_item_reads_with_the_configured_tenants() -> None:
    """The bridge gives the legacy channel the Slack tenant from the configured-systems read."""
    records = _records_with(TABLE_NAME, _legacy_item("inc-legacy"))

    store = build_incident_store(records, _slack_and_google(), _settings())

    result = store.get("inc-legacy")
    assert result.data is not None
    assert result.data.conversation == CONVERSATION
    found = store.find_by_conversation(CONVERSATION)
    assert found.data is not None
    assert found.data.id == "inc-legacy"


def test_system_missing_from_the_read_leaves_its_tenant_out() -> None:
    """Without a Slack tenant the bridge cannot place the legacy channel, so the item is unreadable."""
    records = _records_with(TABLE_NAME, _legacy_item("inc-no-slack"))

    store = build_incident_store(records, _FakeConfiguredSystems({WorkplaceSystem.GOOGLE: GOOGLE_TENANT}), _settings())

    assert store.get("inc-no-slack").error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE


def test_tenants_are_copied_at_build() -> None:
    """A later change to the read's mapping does not reach a store already built."""
    records = _records_with(TABLE_NAME, _legacy_item("inc-copied"))
    systems = _slack_and_google()

    store = build_incident_store(records, systems, _settings())
    systems.mapping.clear()

    result = store.get("inc-copied")
    assert result.data is not None
    assert result.data.conversation == CONVERSATION
