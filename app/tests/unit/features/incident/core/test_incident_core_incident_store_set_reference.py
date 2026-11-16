"""Behavior tests for IncidentStore.set_reference: one reference map, replaced whole, on an end-state record.

The real store writes one update guarded on ``record_version`` and answers with
the incident parsed from the updated item; a legacy item (no record_version)
is a conflict, never rewritten in a mixed shape. Success, replacement, the
missing-incident refusal and the wrong-class error run on the real store over
InMemoryRecordStore and on the in-memory fake. Guard, conflict and failure
cases run on the real store only: a spy over InMemoryRecordStore captures the
guard, and a MagicMock RecordStore returns the backend failure.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any
from unittest.mock import MagicMock

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import ExpectedValue, RecordChange, RecordStore, RecordTable
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.adapters.incident_items import END_STATE_VERSION, RECORD_VERSION
from features.incident.core.domain import (
    ExternalCaseReference,
    PostmortemMeetingReference,
    ReferenceKind,
    ReportReference,
    ResourceReference,
    VideoCallReference,
)
from features.incident.core.store import IncidentStore, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import declared_incident, record_incident_store, seed_legacy_incident

pytestmark = pytest.mark.unit

CHANNEL = "C0INCIDENT"
INCIDENT_ID = "inc-1"
KINDS: list[tuple[ReferenceKind, ResourceReference]] = [
    (
        ReferenceKind.REPORT,
        ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="1DOC", url="https://d/1"),
    ),
    (ReferenceKind.VIDEO_CALL, VideoCallReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="abc-defg-hij")),
    (
        ReferenceKind.POSTMORTEM_MEETING,
        PostmortemMeetingReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="EV1"),
    ),
    (ReferenceKind.EXTERNAL_CASE, ExternalCaseReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="CASE-1")),
]


class GuardSpy(InMemoryRecordStore):
    """InMemoryRecordStore that keeps the guard of every update."""

    def __init__(self) -> None:
        super().__init__()
        self.guards: list[Mapping[str, ExpectedValue] | None] = []

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Mapping[str, ExpectedValue] | None = None,
    ) -> OperationResult:
        self.guards.append(expected)
        return super().update(table, key, changes, expected=expected)


def _real() -> IncidentStore:
    return record_incident_store(InMemoryRecordStore())


STORES: dict[str, Callable[[], IncidentStore]] = {"real": _real, "fake": InMemoryIncidentStore}


@pytest.fixture(params=sorted(STORES))
async def store(request: pytest.FixtureRequest) -> IncidentStore:
    """A real store or fake holding one created incident."""
    created = STORES[request.param]()
    assert (await created.create(declared_incident(INCIDENT_ID))).is_success
    return created


@pytest.mark.parametrize(("kind", "reference"), KINDS, ids=[kind.value for kind, _ in KINDS])
async def test_each_kind_sets_its_reference_and_returns_the_updated_incident(
    store: IncidentStore, kind: ReferenceKind, reference: ResourceReference
) -> None:
    """The answer and a later read both carry the new reference; nothing else changes."""
    result = await store.set_reference(INCIDENT_ID, kind, reference)

    assert result.is_success
    assert result.data is not None
    assert getattr(result.data, kind.value) == reference
    assert (await store.get(INCIDENT_ID)).data == result.data


async def test_a_reference_is_replaced_whole(store: IncidentStore) -> None:
    """A second reference of the kind replaces the first, url included: no field of the old map survives."""
    first = ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="1DOC", url="https://d/1")
    second = ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="2DOC")
    assert (await store.set_reference(INCIDENT_ID, ReferenceKind.REPORT, first)).is_success

    result = await store.set_reference(INCIDENT_ID, ReferenceKind.REPORT, second)

    assert result.data is not None
    assert result.data.report == second


async def test_setting_the_same_reference_twice_is_a_no_op(store: IncidentStore) -> None:
    """The guard still holds after the write, so a repeat or an SDK retry applies the same map again."""
    reference = KINDS[0][1]
    first = await store.set_reference(INCIDENT_ID, ReferenceKind.REPORT, reference)

    second = await store.set_reference(INCIDENT_ID, ReferenceKind.REPORT, reference)

    assert second.is_success
    assert second.data == first.data


async def test_a_missing_incident_is_not_an_incident(store: IncidentStore) -> None:
    """update never creates an item, so an unknown id is NOT_FOUND."""
    result = await store.set_reference("inc-missing", ReferenceKind.REPORT, KINDS[0][1])

    assert (result.status, result.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)


@pytest.mark.parametrize(
    ("kind", "reference"),
    [
        (ReferenceKind.REPORT, VideoCallReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="abc")),
        (ReferenceKind.VIDEO_CALL, ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="1DOC")),
    ],
)
async def test_a_reference_of_another_kind_raises(
    store: IncidentStore, kind: ReferenceKind, reference: ResourceReference
) -> None:
    """Each kind takes its own reference type, so a report is never stored as the video call."""
    with pytest.raises(ValueError, match=kind.value):
        await store.set_reference(INCIDENT_ID, kind, reference)


async def test_the_update_is_guarded_on_the_record_version() -> None:
    """The guard is the end-state version, so only items the current writers own are changed."""
    records = GuardSpy()
    store = record_incident_store(records)
    assert (await store.create(declared_incident(INCIDENT_ID))).is_success

    assert (await store.set_reference(INCIDENT_ID, ReferenceKind.REPORT, KINDS[0][1])).is_success

    assert records.guards == [{"record_version": RECORD_VERSION}]


async def test_a_legacy_item_is_a_conflict_and_stays_unchanged() -> None:
    """An item without record_version is never patched into a mixed shape; the caller gets INCIDENT_RECORD_CONFLICT."""
    records = InMemoryRecordStore()
    seed_legacy_incident(records, CHANNEL, incident_id=INCIDENT_ID)
    store = record_incident_store(records)
    before = (await store.get(INCIDENT_ID)).data

    result = await store.set_reference(INCIDENT_ID, ReferenceKind.REPORT, KINDS[0][1])

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INCIDENT_RECORD_CONFLICT)
    assert (await store.get(INCIDENT_ID)).data == before


async def test_a_store_failure_is_classified_with_a_generic_message() -> None:
    """The backend's status, code and retry hint are kept; its message is not."""
    records = MagicMock(spec=RecordStore)
    records.update.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="throttled: arn:aws:...", error_code="Throttling", retry_after=3
    )

    result = await record_incident_store(records).set_reference(INCIDENT_ID, ReferenceKind.REPORT, KINDS[0][1])

    assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "Throttling", 3)
    assert result.message == "The incident store is unavailable."


async def test_a_missing_table_is_a_store_failure_not_a_missing_incident() -> None:
    """NOT_FOUND carrying the backend's code is a broken store, so it is never read as an unknown incident."""
    records = MagicMock(spec=RecordStore)
    records.update.return_value = OperationResult.error(
        OperationStatus.NOT_FOUND, message="table missing", error_code="ResourceNotFoundException"
    )

    result = await record_incident_store(records).set_reference(INCIDENT_ID, ReferenceKind.REPORT, KINDS[0][1])

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, "ResourceNotFoundException")


async def test_an_item_of_another_record_version_is_a_conflict_and_stays_unchanged() -> None:
    """An end-state item without its binding (version 1) is not the shape this writer owns, so it is refused."""
    records = InMemoryRecordStore()
    store = record_incident_store(records)
    assert (await store.create(declared_incident(INCIDENT_ID))).is_success
    table = incidents_table(get_incident_core_settings().incidents_table)
    item: dict[str, Any] = records.get(table, {"id": INCIDENT_ID}).data or {}
    assert records.put(table, {**item, "record_version": END_STATE_VERSION}).is_success

    result = await store.set_reference(INCIDENT_ID, ReferenceKind.REPORT, KINDS[0][1])

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INCIDENT_RECORD_CONFLICT)
    assert records.get(table, {"id": INCIDENT_ID}).data == {**item, "record_version": END_STATE_VERSION}
