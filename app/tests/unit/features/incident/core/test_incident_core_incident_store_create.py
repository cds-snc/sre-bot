"""Behavior tests for IncidentStore.create: the record alone, the commit point.

create puts the end-state record only where nothing is stored and writes no
binding: chat conversations are attached afterwards (attach_conversation), and
an incident with no surface is complete, worked through the API. The cases
without failure injection run against the real store over InMemoryRecordStore
and the in-memory fake, which must agree. Store failures and the retry
contract run on the real store over FlakyRecordStore, which fails a chosen
table's conditional puts (optionally after the item lands) and records every
write by table, so each assertion names exactly which writes happened.
"""

import dataclasses
from collections.abc import Callable
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.records import RecordTable
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.adapters.incident_items import OPEN_BUCKET, RECORD_VERSION
from features.incident.core.domain import Incident, ReferenceKind, ReportReference
from features.incident.core.store import IncidentStore, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import (
    FlakyRecordStore,
    declared_incident,
    incident_on,
    record_incident_store,
    slack_conversation,
)

pytestmark = pytest.mark.unit

INCIDENT_ID = "inc-1"
RETRY_ID = "inc-2"


def _incidents() -> RecordTable:
    return incidents_table(get_incident_core_settings().incidents_table)


def _real() -> IncidentStore:
    return record_incident_store(InMemoryRecordStore())


STORES: dict[str, Callable[[], IncidentStore]] = {"real": _real, "fake": InMemoryIncidentStore}


@pytest.fixture(params=sorted(STORES))
def store(request: pytest.FixtureRequest) -> IncidentStore:
    """The real store over an empty InMemoryRecordStore, or the in-memory fake."""
    return STORES[request.param]()


def _stored(records: InMemoryRecordStore, key: dict[str, Any]) -> dict[str, Any] | None:
    result = records.get(_incidents(), key)
    return result.data if result.is_success else None


def test_create_returns_the_incident_and_it_is_readable_and_open(store: IncidentStore) -> None:
    """An incident with no surface is complete: read back by id and listed as open."""
    incident = declared_incident(INCIDENT_ID)

    result = store.create(incident)

    assert result.is_success
    assert result.data == incident
    assert store.get(INCIDENT_ID).data == incident
    assert [listed.id for listed in store.list_open().data or []] == [INCIDENT_ID]


def test_an_incident_without_a_surface_is_matched_to_no_conversation(store: IncidentStore) -> None:
    """Nothing binds it, so no conversation lookup returns it."""
    assert store.create(declared_incident(INCIDENT_ID)).is_success

    lookup = store.find_by_conversation(slack_conversation("C0INCIDENT"))

    assert (lookup.status, lookup.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)


def test_create_puts_one_end_state_record_and_no_binding() -> None:
    """One conditional put on the incidents table; the record carries version 2, the open bucket and no conversation copy."""
    records = FlakyRecordStore()

    assert record_incident_store(records).create(declared_incident(INCIDENT_ID)).is_success

    assert records.writes == [(_incidents().name, "put_if_not_exists")]
    record = _stored(records, {"id": INCIDENT_ID})
    assert record is not None
    assert record["record_version"] == RECORD_VERSION == 2
    assert record["open_bucket"] == OPEN_BUCKET
    assert "conversation" not in record
    assert "channel_id" not in record


def test_a_failed_record_write_is_classified_with_a_generic_message() -> None:
    """The store's status, code and retry hint are kept; nothing is stored."""
    records = FlakyRecordStore({_incidents().name: 1})

    result = record_incident_store(records).create(declared_incident(INCIDENT_ID))

    assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "ServiceUnavailable", 2)
    assert result.message == "The incident store is unavailable."
    assert _stored(records, {"id": INCIDENT_ID}) is None


@pytest.mark.parametrize("landed", [False, True], ids=["failed", "lost-response"])
def test_a_same_id_retry_converges_on_one_record(landed: bool) -> None:
    """Whether the write failed or landed with its response lost, retrying the same id stores the record once."""
    records = FlakyRecordStore({_incidents().name: 1}, landed=landed)
    store = record_incident_store(records)
    incident = declared_incident(INCIDENT_ID)
    assert not store.create(incident).is_success

    retry = store.create(incident)

    assert retry.is_success
    assert retry.data == incident
    assert len(records.read_all(_incidents(), max_items=10).data or []) == 1


def test_a_new_id_retry_after_a_lost_response_leaves_an_orphan_open_incident() -> None:
    """The documented residual: two open records, neither with a surface, so no conversation is made ambiguous."""
    records = FlakyRecordStore({_incidents().name: 1}, landed=True)
    store = record_incident_store(records)
    assert not store.create(declared_incident(INCIDENT_ID)).is_success

    assert store.create(declared_incident(RETRY_ID)).is_success

    assert sorted(listed.id for listed in store.list_open().data or []) == [INCIDENT_ID, RETRY_ID]


def test_a_replay_returns_the_stored_incident_and_rewrites_nothing(store: IncidentStore) -> None:
    """A second create of the same id answers what is stored, including a reference set in between."""
    incident = declared_incident(INCIDENT_ID)
    assert store.create(incident).is_success
    report = ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="1DOC")
    assert store.set_reference(INCIDENT_ID, ReferenceKind.REPORT, report).is_success

    replay = store.create(dataclasses.replace(incident, title="Changed on replay"))

    assert replay.is_success
    assert replay.data == dataclasses.replace(incident, report=report)
    assert store.get(INCIDENT_ID).data == dataclasses.replace(incident, report=report)


def test_a_replay_on_the_real_store_writes_no_item() -> None:
    """The conditional put finds the item, so the stored record is unchanged."""
    records = FlakyRecordStore()
    store = record_incident_store(records)
    incident = declared_incident(INCIDENT_ID)
    assert store.create(incident).is_success
    before = _stored(records, {"id": INCIDENT_ID})

    assert store.create(dataclasses.replace(incident, title="Changed")).is_success

    assert _stored(records, {"id": INCIDENT_ID}) == before


@pytest.mark.parametrize(
    ("incident", "message"),
    [
        (dataclasses.replace(declared_incident(INCIDENT_ID), status=IncidentStatus.CLOSED), "open"),
        (dataclasses.replace(declared_incident(INCIDENT_ID), status=IncidentStatus.IN_PROGRESS), "open"),
        (incident_on("C0INCIDENT", INCIDENT_ID), "attach_conversation"),
    ],
    ids=["closed", "in-progress", "with-conversation"],
)
@pytest.mark.parametrize("kind", sorted(STORES))
def test_a_caller_error_raises_and_writes_nothing(incident: Incident, message: str, kind: str) -> None:
    """Only a new open incident is created; its conversation arrives only through attach_conversation."""
    store = STORES[kind]()

    with pytest.raises(ValueError, match=message):
        store.create(incident)

    assert store.get(INCIDENT_ID).status is OperationStatus.NOT_FOUND
