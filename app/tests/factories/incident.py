"""Incident records and stores for tests of the incident subdomains.

Each incident sits on a Slack conversation under one tenant, so a test that
resolves a conversation through ``InMemoryIncidentStore`` exercises the same
system, tenant and channel match the real store applies.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from contracts.operations import OperationResult
from contracts.records import ExpectedValue, RecordChange, RecordStore, RecordTable
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.api import StatusUpdateStore, build_status_update_store
from features.incident.core.domain import ConversationReference, Incident
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.services import FakeServiceScopeOpener

SLACK_TENANT = "T0SLACK"
DECLARED_AT = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def slack_conversation(channel_id: str, *, tenant: str = SLACK_TENANT) -> ConversationReference:
    """The Slack conversation reference of ``channel_id`` under ``tenant``."""
    return ConversationReference(system=WorkplaceSystem.SLACK, tenant=tenant, vendor_id=channel_id)


def incident_on(
    channel_id: str,
    incident_id: str,
    *,
    tenant: str = SLACK_TENANT,
    security_incident: bool = False,
) -> Incident:
    """An open incident whose conversation is ``channel_id`` under ``tenant``."""
    return Incident(
        id=incident_id,
        title=f"Incident {incident_id}",
        status=IncidentStatus.OPEN,
        declared_by="U0DECLARER",
        declared_at=DECLARED_AT,
        security_incident=security_incident,
        conversation=slack_conversation(channel_id, tenant=tenant),
    )


def incident_store_with(*incidents: Incident) -> InMemoryIncidentStore:
    """An in-memory incident store seeded with ``incidents``."""
    store = InMemoryIncidentStore()
    for incident in incidents:
        store.seed(incident)
    return store


class FakeConfiguredSystems(ConfiguredSystems):
    """Configured systems fixed at construction."""

    def __init__(self, tenants: Mapping[WorkplaceSystem, str]) -> None:
        self._tenants = dict(tenants)

    def tenants(self) -> Mapping[WorkplaceSystem, str]:
        """Return the tenant id of each configured system."""
        return self._tenants


def incident_scopes(
    records: RecordStore | None = None,
    *,
    tenants: Mapping[WorkplaceSystem, str] | None = None,
) -> FakeServiceScopeOpener:
    """A scope opener resolving the RecordStore and ConfiguredSystems an incident entry point needs.

    ``records`` defaults to an empty ``InMemoryRecordStore``; ``tenants``
    defaults to Slack configured under ``SLACK_TENANT``.
    """
    return FakeServiceScopeOpener(
        {
            RecordStore: records if records is not None else InMemoryRecordStore(),
            ConfiguredSystems: FakeConfiguredSystems({WorkplaceSystem.SLACK: SLACK_TENANT} if tenants is None else tenants),
        }
    )


def status_update_store_in(records: RecordStore) -> StatusUpdateStore:
    """The status-update store an entry point builds over ``records`` with the configured incident settings.

    Seeding or reading through it observes the same table the handlers write
    when they are given ``incident_scopes(records)``.
    """
    return build_status_update_store(records, get_incident_core_settings())


class CountingRecordStore(InMemoryRecordStore):
    """In-memory record store that records each write by operation name, so a test can prove which writes happened."""

    def __init__(self) -> None:
        super().__init__()
        self.writes: list[str] = []

    def put(self, table: RecordTable, item: dict[str, Any]) -> OperationResult:
        self.writes.append("put")
        return super().put(table, item)

    def put_if_not_exists(self, table: RecordTable, item: dict[str, Any]) -> OperationResult:
        self.writes.append("put_if_not_exists")
        return super().put_if_not_exists(table, item)

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Mapping[str, ExpectedValue] | None = None,
    ) -> OperationResult:
        self.writes.append("update")
        return super().update(table, key, changes, expected=expected)

    def delete(self, table: RecordTable, key: dict[str, Any]) -> OperationResult:
        self.writes.append("delete")
        return super().delete(table, key)
