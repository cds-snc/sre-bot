"""Incident records and stores for tests of the incident subdomains.

Each incident sits on a Slack conversation under one tenant, so a test that
resolves a conversation through ``InMemoryIncidentStore`` exercises the same
system, tenant and channel match the real store applies.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from contracts.operations import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import ExpectedValue, RecordChange, RecordStore, RecordTable
from contracts.workplace import ConfiguredSystems, WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.api import StatusUpdateStore, build_status_update_store
from features.incident.core.domain import BindingKind, ConversationReference, Incident, IncidentBinding
from features.incident.core.store import RecordIncidentStore, bindings_table, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.services import FakeServiceScopeOpener

SLACK_TENANT = "T0SLACK"
GOOGLE_TENANT = "C0GOOGLE"
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


def declared_incident(incident_id: str, *, security_incident: bool = False) -> Incident:
    """An open incident as declare creates it: no conversation yet, since one is attached after the record."""
    return Incident(
        id=incident_id,
        title=f"Incident {incident_id}",
        status=IncidentStatus.OPEN,
        declared_by="U0DECLARER",
        declared_at=DECLARED_AT,
        security_incident=security_incident,
    )


def binding_on(
    channel_id: str,
    incident_id: str,
    *,
    tenant: str = SLACK_TENANT,
    primary: bool = True,
    archived_at: datetime | None = None,
    kind: BindingKind = BindingKind.CHAT_CONVERSATION,
) -> IncidentBinding:
    """A binding of ``incident_id`` to the Slack conversation ``channel_id`` under ``tenant``."""
    return IncidentBinding(
        incident_id=incident_id,
        kind=kind,
        system=WorkplaceSystem.SLACK,
        tenant=tenant,
        vendor_id=channel_id,
        primary=primary,
        bound_by="U0DECLARER",
        bound_at=DECLARED_AT,
        archived_at=archived_at,
    )


def record_incident_store(
    records: RecordStore,
    *,
    tenants: Mapping[WorkplaceSystem, str] | None = None,
    table: RecordTable | None = None,
    bindings: RecordTable | None = None,
) -> RecordIncidentStore:
    """The real incident store over ``records``.

    ``tenants`` defaults to Slack under ``SLACK_TENANT``; ``table`` and ``bindings``
    default to the declared incidents and bindings tables under their configured names.
    """
    settings = get_incident_core_settings()
    return RecordIncidentStore(
        records,
        incidents_table(settings.incidents_table) if table is None else table,
        {WorkplaceSystem.SLACK: SLACK_TENANT} if tenants is None else dict(tenants),
        bindings=bindings_table(settings.bindings_table) if bindings is None else bindings,
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


def seed_legacy_incident(
    records: RecordStore, channel_id: str, *, incident_id: str = "inc-legacy", report_url: str | None = None
) -> None:
    """Store a legacy incident item on ``channel_id`` in the configured incidents table, as the legacy declare wrote it.

    The read path upgrades it through the legacy item bridge, so ``report_url`` becomes
    the record's report reference only when the Google tenant is configured. Storing
    again under the same ``incident_id`` replaces the item.
    """
    item: dict[str, Any] = {
        "id": incident_id,
        "channel_id": channel_id,
        "name": f"Incident {incident_id}",
        "user_id": "U0DECLARER",
        "teams": ["Platform"],
        "status": "Open",
        "created_at": "1760536800.0",
    }
    if report_url is not None:
        item["report_url"] = report_url
    assert records.put(incidents_table(get_incident_core_settings().incidents_table), item).is_success


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


class FlakyRecordStore(InMemoryRecordStore):
    """In-memory record store whose conditional puts and updates fail on chosen tables, and that records every write.

    ``fail_puts`` and ``fail_updates`` map a table name to how many of its next
    conditional puts or updates fail with a transient error. With ``landed`` a
    failing put still stores the item,
    standing in for a write that reached the table but whose response was lost
    past the SDK retries. ``writes`` lists each write as (table name, operation).
    """

    def __init__(
        self,
        fail_puts: Mapping[str, int] | None = None,
        *,
        landed: bool = False,
        fail_updates: Mapping[str, int] | None = None,
    ) -> None:
        super().__init__()
        self.fail_puts = dict(fail_puts or {})
        self.fail_updates = dict(fail_updates or {})
        self.landed = landed
        self.writes: list[tuple[str, str]] = []

    def put_if_not_exists(self, table: RecordTable, item: dict[str, Any]) -> OperationResult:
        self.writes.append((table.name, "put_if_not_exists"))
        if self.fail_puts.get(table.name, 0) > 0:
            self.fail_puts[table.name] -= 1
            if self.landed:
                super().put_if_not_exists(table, item)
            return _unavailable()
        return super().put_if_not_exists(table, item)

    def put(self, table: RecordTable, item: dict[str, Any]) -> OperationResult:
        self.writes.append((table.name, "put"))
        return super().put(table, item)

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Mapping[str, ExpectedValue] | None = None,
    ) -> OperationResult:
        self.writes.append((table.name, "update"))
        if self.fail_updates.get(table.name, 0) > 0:
            self.fail_updates[table.name] -= 1
            return _unavailable()
        return super().update(table, key, changes, expected=expected)


def _unavailable() -> OperationResult:
    return OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="backend unavailable", error_code="ServiceUnavailable", retry_after=2
    )
