"""Behavior tests for upgrade on write: a field write on an item below the current version raises it in the same update.

The store plans the upgrade with ``plan_item_upgrade``, the function the legacy
upgrade job uses, so the written item must equal the job's plan applied to the
stored item, plus the change. The binding is put first; the record update
carries the upgrade, the change and the version marker. Every case runs on the
real store over InMemoryRecordStore or FlakyRecordStore (which fails a chosen
table's puts and records every write by table), reading the tables back.
"""

from datetime import timedelta
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.records import RecordTable, SetAttribute
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import IncidentRole, IncidentStatus, Severity
from features.incident.core.adapters.binding_items import binding_item
from features.incident.core.adapters.incident_items import END_STATE_VERSION, RECORD_VERSION
from features.incident.core.adapters.item_upgrade import ItemUpgrade, plan_item_upgrade
from features.incident.core.domain import IncidentChanges
from features.incident.core.store import bindings_table, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import (
    DECLARED_AT,
    SLACK_TENANT,
    FlakyRecordStore,
    binding_on,
    declared_incident,
    record_incident_store,
    seed_legacy_incident,
)

pytestmark = pytest.mark.unit

CHANNEL = "C0INCIDENT"
INCIDENT_ID = "inc-legacy"
BY = "U0EDITOR"
AT = DECLARED_AT + timedelta(hours=1)
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT}


def _incidents() -> RecordTable:
    return incidents_table(get_incident_core_settings().incidents_table)


def _bindings() -> RecordTable:
    return bindings_table(get_incident_core_settings().bindings_table)


def _item(records: InMemoryRecordStore) -> dict[str, Any]:
    return records.get(_incidents(), {"id": INCIDENT_ID}).data or {}


def _planned(item: dict[str, Any]) -> tuple[dict[str, Any], ItemUpgrade]:
    """Return ``item`` as the legacy upgrade job would leave it, and the plan."""
    plan = plan_item_upgrade(item, TENANTS)
    assert isinstance(plan, ItemUpgrade)
    upgraded = dict(item)
    for change in plan.changes:
        assert isinstance(change, SetAttribute)
        upgraded[change.attribute] = change.value
    return upgraded, plan


async def test_a_legacy_item_gets_its_binding_then_one_update_with_the_upgrade_and_the_change() -> None:
    """The written item equals the job's plan plus the new severity; the binding is the plan's, put first."""
    records = FlakyRecordStore()
    seed_legacy_incident(records, CHANNEL, incident_id=INCIDENT_ID)
    expected_item, plan = _planned(_item(records))
    records.writes.clear()

    result = await record_incident_store(records).update_fields(
        INCIDENT_ID, IncidentChanges(severity=Severity.SEV2), by=BY, at=AT
    )

    assert result.data is not None
    assert result.data.severity is Severity.SEV2
    assert _item(records) == {**expected_item, "severity": int(Severity.SEV2)}
    assert plan.binding is not None
    assert records.get(_bindings(), dict(_binding_key(plan.binding))).data == binding_item(plan.binding)
    assert records.writes[:2] == [(_bindings().name, "put_if_not_exists"), (_incidents().name, "update")]


def _binding_key(binding: Any) -> dict[str, Any]:
    item = binding_item(binding)
    table = _bindings()
    assert table.key.sort is not None
    return {table.key.partition: item[table.key.partition], table.key.sort: item[table.key.sort]}


async def test_a_failed_binding_put_leaves_the_item_untouched() -> None:
    """Side records first: without its binding, the item is never raised to the version that promises one."""
    records = FlakyRecordStore(fail_puts={_bindings().name: 1})
    seed_legacy_incident(records, CHANNEL, incident_id=INCIDENT_ID)
    before = _item(records)

    result = await record_incident_store(records).update_fields(
        INCIDENT_ID, IncidentChanges(severity=Severity.SEV2), by=BY, at=AT
    )

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert _item(records) == before


async def test_an_end_state_item_without_its_binding_is_raised_with_its_binding() -> None:
    """A version-1 item gets the primary binding of its conversation and record_version 2 with the change."""
    records = InMemoryRecordStore()
    store = record_incident_store(records)
    assert (await store.create(declared_incident(INCIDENT_ID))).is_success
    assert (await store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID))).is_success
    item = _item(records)
    assert records.put(_incidents(), {**item, "record_version": END_STATE_VERSION}).is_success
    assert records.delete(_bindings(), _binding_key(binding_on(CHANNEL, INCIDENT_ID))).is_success

    result = await store.set_roles(INCIDENT_ID, {IncidentRole.INCIDENT_COMMANDER: "U0IC"})

    assert result.data is not None
    assert result.data.incident_commander == "U0IC"
    assert _item(records)["record_version"] == RECORD_VERSION
    assert records.get(_bindings(), _binding_key(binding_on(CHANNEL, INCIDENT_ID))).data is not None


async def test_an_unreadable_legacy_item_is_refused_with_the_field_logged_and_nothing_written() -> None:
    """An item the bridge cannot read cannot be upgraded, so it is INCIDENT_RECORD_UNREADABLE and left for the job's report."""
    records = FlakyRecordStore()
    seed_legacy_incident(records, CHANNEL, incident_id=INCIDENT_ID)
    assert records.put(_incidents(), {**_item(records), "status": "Exploded"}).is_success
    records.writes.clear()

    with capture_logs() as logs:
        result = await record_incident_store(records).update_fields(INCIDENT_ID, IncidentChanges(title="x"), by=BY, at=AT)

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INCIDENT_RECORD_UNREADABLE)
    assert [log["field"] for log in logs if log["event"] == "incident_record_unreadable"] == ["status"]
    assert records.writes == []


async def test_an_open_legacy_item_without_a_channel_is_refused() -> None:
    """No conversation means no binding, so the open item cannot reach the version that promises one."""
    records = FlakyRecordStore()
    seed_legacy_incident(records, CHANNEL, incident_id=INCIDENT_ID)
    item = {key: value for key, value in _item(records).items() if key != "channel_id"}
    assert records.put(_incidents(), item).is_success
    records.writes.clear()

    with capture_logs() as logs:
        result = await record_incident_store(records).update_fields(INCIDENT_ID, IncidentChanges(title="x"), by=BY, at=AT)

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INCIDENT_RECORD_UNREADABLE)
    assert [log["field"] for log in logs if log["event"] == "incident_record_unreadable"] == ["conversation"]
    assert records.writes == []


async def test_an_item_above_the_current_version_is_a_conflict() -> None:
    """A newer writer's shape is never rewritten by this one."""
    records = InMemoryRecordStore()
    store = record_incident_store(records)
    assert (await store.create(declared_incident(INCIDENT_ID))).is_success
    newer = {**_item(records), "record_version": RECORD_VERSION + 1}
    assert records.put(_incidents(), newer).is_success

    result = await store.update_fields(INCIDENT_ID, IncidentChanges(title="x"), by=BY, at=AT)

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INCIDENT_RECORD_CONFLICT)
    assert _item(records) == newer


async def test_closing_an_open_legacy_item_drops_the_open_index_attributes_the_plan_would_set() -> None:
    """The close removes open_bucket and opened_at in the same update the upgrade would have set them in."""
    records = InMemoryRecordStore()
    seed_legacy_incident(records, CHANNEL, incident_id=INCIDENT_ID)
    expected_item, _ = _planned(_item(records))
    store = record_incident_store(records)

    result = await store.set_status(INCIDENT_ID, IncidentStatus.CLOSED, at=AT)

    assert result.data is not None
    assert result.data.status is IncidentStatus.CLOSED
    expected_item = {key: value for key, value in expected_item.items() if key not in {"open_bucket", "opened_at"}}
    assert _item(records) == {**expected_item, "status": IncidentStatus.CLOSED.value}
    listed = (await store.list_open()).data
    assert listed is not None
    assert INCIDENT_ID not in {incident.id for incident in listed}


async def test_a_replay_on_a_legacy_item_writes_nothing() -> None:
    """A change the item already holds is no write at all: the item stays legacy until a real change or the job."""
    records = FlakyRecordStore()
    seed_legacy_incident(records, CHANNEL, incident_id=INCIDENT_ID)
    before = _item(records)
    records.writes.clear()

    result = await record_incident_store(records).set_status(INCIDENT_ID, IncidentStatus.OPEN, at=AT)

    assert result.data is not None
    assert result.data.status is IncidentStatus.OPEN
    assert records.writes == []
    assert _item(records) == before


async def test_removal_replaces_the_plans_set_of_the_same_attribute() -> None:
    """One action per attribute: a cleared role drops the upgrade's Set of it rather than sending both."""
    records = InMemoryRecordStore()
    seed_legacy_incident(records, CHANNEL, incident_id=INCIDENT_ID)
    assert records.put(_incidents(), {**_item(records), "incident_commander": "U0OLD"}).is_success
    store = record_incident_store(records)

    result = await store.set_roles(INCIDENT_ID, {IncidentRole.INCIDENT_COMMANDER: None})

    assert result.data is not None
    assert result.data.incident_commander is None
    assert "incident_commander" not in _item(records)
