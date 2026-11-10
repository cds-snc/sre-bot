"""Behavior tests for IncidentStore.create: the binding, then the record.

create puts the incident's primary chat binding and then its end-state record,
both only where nothing is stored; the record is the commit point. The cases
without failure injection run against the real store over InMemoryRecordStore
and the in-memory fake, which must agree. Write order, store failures and the
retry contract run on the real store over FlakyRecordStore, which fails a
chosen table's conditional puts (optionally after the item lands) and records
every write by table, so each assertion names exactly which writes happened.
"""

import dataclasses
from collections.abc import Callable
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.records import RecordTable
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.binding_items import binding_item
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.adapters.incident_items import OPEN_BUCKET, RECORD_VERSION
from features.incident.core.domain import Incident, IncidentBinding, ReferenceKind, ReportReference
from features.incident.core.store import IncidentStore, bindings_table, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import (
    DECLARED_AT,
    SLACK_TENANT,
    FlakyRecordStore,
    binding_on,
    incident_on,
    record_incident_store,
    slack_conversation,
)

pytestmark = pytest.mark.unit

CHANNEL = "C0INCIDENT"
INCIDENT_ID = "inc-1"
RETRY_ID = "inc-2"


def _incidents() -> RecordTable:
    return incidents_table(get_incident_core_settings().incidents_table)


def _bindings() -> RecordTable:
    return bindings_table(get_incident_core_settings().bindings_table)


def _real() -> IncidentStore:
    return record_incident_store(InMemoryRecordStore())


STORES: dict[str, Callable[[], IncidentStore]] = {"real": _real, "fake": InMemoryIncidentStore}


@pytest.fixture(params=sorted(STORES))
def store(request: pytest.FixtureRequest) -> IncidentStore:
    """The real store over an empty InMemoryRecordStore, or the in-memory fake."""
    return STORES[request.param]()


def _stored(records: InMemoryRecordStore, table: RecordTable, key: dict[str, Any]) -> dict[str, Any] | None:
    result = records.get(table, key)
    return result.data if result.is_success else None


def _binding_key(binding: IncidentBinding) -> dict[str, Any]:
    item = binding_item(binding)
    return {"incident_id": item["incident_id"], "binding_key": item["binding_key"]}


def test_create_returns_the_incident_and_the_lookup_finds_it(store: IncidentStore) -> None:
    """The created incident is read back by id, listed as open and found through its conversation."""
    incident = incident_on(CHANNEL, INCIDENT_ID)

    result = store.create(incident, binding_on(CHANNEL, INCIDENT_ID))

    assert result.is_success
    assert result.data == incident
    assert store.get(INCIDENT_ID).data == incident
    assert [listed.id for listed in store.list_open().data or []] == [INCIDENT_ID]
    assert store.find_by_conversation(slack_conversation(CHANNEL)).data == incident


def test_create_stores_the_binding_item_and_the_end_state_record() -> None:
    """The binding is exactly binding_item's output; the record carries version 2, the open bucket and channel_id."""
    records = InMemoryRecordStore()
    binding = binding_on(CHANNEL, INCIDENT_ID)

    assert record_incident_store(records).create(incident_on(CHANNEL, INCIDENT_ID), binding).is_success

    assert _stored(records, _bindings(), _binding_key(binding)) == binding_item(binding)
    record = _stored(records, _incidents(), {"id": INCIDENT_ID})
    assert record is not None
    assert record["record_version"] == RECORD_VERSION == 2
    assert record["open_bucket"] == OPEN_BUCKET
    assert record["channel_id"] == CHANNEL
    assert record["conversation"] == {"system": "slack", "tenant": SLACK_TENANT, "vendor_id": CHANNEL}


def test_the_by_channel_fallback_agrees_with_the_binding() -> None:
    """With the binding gone, the record's own conversation still answers the same incident."""
    records = InMemoryRecordStore()
    binding = binding_on(CHANNEL, INCIDENT_ID)
    store = record_incident_store(records)
    assert store.create(incident_on(CHANNEL, INCIDENT_ID), binding).is_success

    assert records.delete(_bindings(), _binding_key(binding)).is_success

    assert store.find_by_conversation(slack_conversation(CHANNEL)).data == incident_on(CHANNEL, INCIDENT_ID)


def test_the_binding_is_written_before_the_record() -> None:
    """The record is the commit point, so its put comes last."""
    records = FlakyRecordStore()

    assert record_incident_store(records).create(incident_on(CHANNEL, INCIDENT_ID), binding_on(CHANNEL, INCIDENT_ID)).is_success

    assert records.writes == [(_bindings().name, "put_if_not_exists"), (_incidents().name, "put_if_not_exists")]


def test_a_failed_binding_write_stops_before_the_record() -> None:
    """No record is attempted without its binding; the error carries the store's classification and a generic message."""
    records = FlakyRecordStore({_bindings().name: 1})

    with capture_logs() as logs:
        result = record_incident_store(records).create(incident_on(CHANNEL, INCIDENT_ID), binding_on(CHANNEL, INCIDENT_ID))

    assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "ServiceUnavailable", 2)
    assert result.message == "The incident store is unavailable."
    assert records.writes == [(_bindings().name, "put_if_not_exists")]
    assert _stored(records, _incidents(), {"id": INCIDENT_ID}) is None
    failures = [log for log in logs if log["event"] == "incident_store_failed"]
    assert [(log["operation"], log["table"]) for log in failures] == [("create", _bindings().name)]


def test_a_failed_record_write_leaves_a_binding_no_lookup_returns() -> None:
    """The dangling binding names no record, so the conversation is no incident rather than ambiguous."""
    records = FlakyRecordStore({_incidents().name: 1})
    binding = binding_on(CHANNEL, INCIDENT_ID)
    store = record_incident_store(records)

    result = store.create(incident_on(CHANNEL, INCIDENT_ID), binding)

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.message == "The incident store is unavailable."
    assert _stored(records, _bindings(), _binding_key(binding)) is not None
    lookup = store.find_by_conversation(slack_conversation(CHANNEL))
    assert (lookup.status, lookup.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)


def test_a_new_id_retry_after_a_failed_record_write_resolves_to_the_new_incident() -> None:
    """The first binding stays dangling and never counts; the retry's binding and record answer the lookup."""
    records = FlakyRecordStore({_incidents().name: 1})
    store = record_incident_store(records)
    assert not store.create(incident_on(CHANNEL, INCIDENT_ID), binding_on(CHANNEL, INCIDENT_ID)).is_success

    retry = store.create(incident_on(CHANNEL, RETRY_ID), binding_on(CHANNEL, RETRY_ID))

    assert retry.is_success
    assert store.find_by_conversation(slack_conversation(CHANNEL)).data == incident_on(CHANNEL, RETRY_ID)
    assert _stored(records, _bindings(), _binding_key(binding_on(CHANNEL, INCIDENT_ID))) is not None
    assert _stored(records, _bindings(), _binding_key(binding_on(CHANNEL, RETRY_ID))) is not None


@pytest.mark.parametrize("landed", [False, True], ids=["failed", "lost-response"])
def test_a_same_id_retry_converges_on_one_binding_and_one_record(landed: bool) -> None:
    """Whether the record write failed or landed with its response lost, retrying the same id stores each item once."""
    records = FlakyRecordStore({_incidents().name: 1}, landed=landed)
    store = record_incident_store(records)
    incident = incident_on(CHANNEL, INCIDENT_ID)
    assert not store.create(incident, binding_on(CHANNEL, INCIDENT_ID)).is_success

    retry = store.create(incident, binding_on(CHANNEL, INCIDENT_ID))

    assert retry.is_success
    assert retry.data == incident
    assert len(records.read_all(_bindings(), max_items=10).data or []) == 1
    assert len(records.read_all(_incidents(), max_items=10).data or []) == 1
    assert store.find_by_conversation(slack_conversation(CHANNEL)).data == incident


def test_a_new_id_retry_after_a_lost_record_response_is_ambiguous() -> None:
    """The documented residual: both records exist, so the conversation fails closed rather than picking one."""
    records = FlakyRecordStore({_incidents().name: 1}, landed=True)
    store = record_incident_store(records)
    assert not store.create(incident_on(CHANNEL, INCIDENT_ID), binding_on(CHANNEL, INCIDENT_ID)).is_success
    assert store.create(incident_on(CHANNEL, RETRY_ID), binding_on(CHANNEL, RETRY_ID)).is_success

    lookup = store.find_by_conversation(slack_conversation(CHANNEL))

    assert (lookup.status, lookup.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION)


def test_a_replay_returns_the_stored_incident_and_rewrites_nothing(store: IncidentStore) -> None:
    """A second create of the same id is a no-op that answers what is stored, including a reference set in between."""
    incident = incident_on(CHANNEL, INCIDENT_ID)
    binding = binding_on(CHANNEL, INCIDENT_ID)
    assert store.create(incident, binding).is_success
    report = ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="1DOC")
    updated = store.set_reference(INCIDENT_ID, ReferenceKind.REPORT, report)
    assert updated.is_success

    replay = store.create(dataclasses.replace(incident, title="Changed on replay"), binding)

    assert replay.is_success
    assert replay.data == dataclasses.replace(incident, report=report)
    assert store.get(INCIDENT_ID).data == dataclasses.replace(incident, report=report)


def test_a_replay_on_the_real_store_writes_no_item() -> None:
    """Both conditional puts find their items, so the stored record is byte-for-byte unchanged."""
    records = FlakyRecordStore()
    store = record_incident_store(records)
    incident = incident_on(CHANNEL, INCIDENT_ID)
    assert store.create(incident, binding_on(CHANNEL, INCIDENT_ID)).is_success
    before = _stored(records, _incidents(), {"id": INCIDENT_ID})

    assert store.create(dataclasses.replace(incident, title="Changed"), binding_on(CHANNEL, INCIDENT_ID)).is_success

    assert _stored(records, _incidents(), {"id": INCIDENT_ID}) == before


def _closed() -> tuple[Incident, IncidentBinding]:
    return dataclasses.replace(incident_on(CHANNEL, INCIDENT_ID), status=IncidentStatus.CLOSED), binding_on(CHANNEL, INCIDENT_ID)


def _in_progress() -> tuple[Incident, IncidentBinding]:
    return dataclasses.replace(incident_on(CHANNEL, INCIDENT_ID), status=IncidentStatus.IN_PROGRESS), binding_on(
        CHANNEL, INCIDENT_ID
    )


def _no_conversation() -> tuple[Incident, IncidentBinding]:
    return dataclasses.replace(incident_on(CHANNEL, INCIDENT_ID), conversation=None), binding_on(CHANNEL, INCIDENT_ID)


def _other_incident() -> tuple[Incident, IncidentBinding]:
    return incident_on(CHANNEL, INCIDENT_ID), binding_on(CHANNEL, RETRY_ID)


def _not_primary() -> tuple[Incident, IncidentBinding]:
    return incident_on(CHANNEL, INCIDENT_ID), binding_on(CHANNEL, INCIDENT_ID, primary=False)


def _archived() -> tuple[Incident, IncidentBinding]:
    return incident_on(CHANNEL, INCIDENT_ID), binding_on(CHANNEL, INCIDENT_ID, archived_at=DECLARED_AT)


def _other_channel() -> tuple[Incident, IncidentBinding]:
    return incident_on(CHANNEL, INCIDENT_ID), binding_on("C0OTHER", INCIDENT_ID)


def _other_tenant() -> tuple[Incident, IncidentBinding]:
    return incident_on(CHANNEL, INCIDENT_ID), binding_on(CHANNEL, INCIDENT_ID, tenant="T0OTHER")


def _other_system() -> tuple[Incident, IncidentBinding]:
    binding = dataclasses.replace(binding_on(CHANNEL, INCIDENT_ID), system=WorkplaceSystem.GOOGLE)
    return incident_on(CHANNEL, INCIDENT_ID), binding


@pytest.mark.parametrize(
    ("case", "message"),
    [
        (_closed, "open"),
        (_in_progress, "open"),
        (_no_conversation, "conversation"),
        (_other_incident, "incident_id"),
        (_not_primary, "primary"),
        (_archived, "archived"),
        (_other_channel, "conversation"),
        (_other_tenant, "conversation"),
        (_other_system, "conversation"),
    ],
    ids=lambda value: getattr(value, "__name__", value),
)
def test_a_caller_error_raises_and_writes_nothing(case: Callable[[], tuple[Incident, IncidentBinding]], message: str) -> None:
    """Only a new open incident with its own active primary binding on its conversation can be created."""
    records = FlakyRecordStore()
    incident, binding = case()

    with pytest.raises(ValueError, match=message):
        record_incident_store(records).create(incident, binding)

    assert records.writes == []


@pytest.mark.parametrize(
    "case",
    [_closed, _no_conversation, _other_incident, _not_primary, _archived, _other_channel, _other_tenant, _other_system],
)
def test_the_fake_refuses_the_same_caller_errors(case: Callable[[], tuple[Incident, IncidentBinding]]) -> None:
    """The fake shares the validation, so a test against it cannot create what the real store refuses."""
    store = InMemoryIncidentStore()
    incident, binding = case()

    with pytest.raises(ValueError):
        store.create(incident, binding)

    assert store.get(INCIDENT_ID).status is OperationStatus.NOT_FOUND


def test_the_same_channel_under_another_tenant_is_not_matched(store: IncidentStore) -> None:
    """A created incident is found only through its own tenant's conversation."""
    assert store.create(incident_on(CHANNEL, INCIDENT_ID), binding_on(CHANNEL, INCIDENT_ID)).is_success

    lookup = store.find_by_conversation(slack_conversation(CHANNEL, tenant="T0OTHER"))

    assert (lookup.status, lookup.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)
