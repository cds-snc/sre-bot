"""Behavior tests for the records-backed StatusUpdateStore.

The store runs over ``InMemoryRecordStore``, which holds the records
contract's observable rules (full-key conditional create, guarded atomic
update, key-condition queries with order and limit), so each test asserts what
a caller sees and, for the item layout, the exact stored item: the attributes
and keys the provisioned table already holds. Wire-level DynamoDB behaviour
(serialization, pagination, the replay-safe conditional put) is covered by the
records contract's own tests. Backend failures come from a stub ``RecordStore``
returning classified error results, and their assertions check the
classification plus a message free of backend text.
"""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import RecordChange, RecordQuery, RecordStore, RecordTable
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateStore,
    StatusUpdateText,
)
from features.incident.core.store import RecordStatusUpdateStore, status_updates_table
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

TABLE = status_updates_table("sre_bot_incident_status_updates")
INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"
OTHER_INCIDENT_ID = "1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9"
PK = f"INCIDENT#{INCIDENT_ID}"
BACKEND_DETAIL = "backend detail that must not reach callers"
AT = datetime(2026, 10, 7, 14, 0, tzinfo=UTC)
LATER = datetime(2026, 10, 7, 14, 20, tzinfo=UTC)
PUBLISHED_AT = datetime(2026, 10, 7, 14, 40, tzinfo=UTC)

EN = StatusUpdateText(
    affected_service="GC Notify", impact="Emails are delayed.", current_action="Restarting workers.", workaround=""
)
FR = StatusUpdateText(
    affected_service="Notification GC",
    impact="Les courriels sont retardés.",
    current_action="Redémarrage des processus.",
    workaround="",
)

DRAFT = StatusUpdate(
    incident_id=INCIDENT_ID,
    sequence=1,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.INVESTIGATING,
    en=EN,
    fr=FR,
    next_update_at=datetime(2026, 10, 7, 14, 30, tzinfo=UTC),
    author="U0AUTHOR",
    transcript_cutoff=datetime(2026, 10, 7, 13, 58, tzinfo=UTC),
    transcript_fingerprint="fp-1",
    created_at=AT,
)
APPROVED = replace(
    DRAFT,
    state=StatusUpdateState.APPROVED,
    stage=StatusUpdateStage.IDENTIFIED,
    en=replace(EN, current_action="Edited."),
    approver="U0APPROVER",
    approved_at=LATER,
)
PUBLISHED = replace(APPROVED, state=StatusUpdateState.PUBLISHED, published_at=PUBLISHED_AT, published_by="U0PUBLISHER")


def _text_item(text: StatusUpdateText) -> dict[str, Any]:
    return {
        "affected_service": text.affected_service,
        "impact": text.impact,
        "current_action": text.current_action,
        "workaround": text.workaround,
    }


DRAFT_ITEM: dict[str, Any] = {
    "PK": PK,
    "SK": "UPDATE#000001",
    "incident_id": INCIDENT_ID,
    "sequence": 1,
    "state": "draft",
    "stage": "investigating",
    "en": _text_item(EN),
    "fr": _text_item(FR),
    "next_update_at": "2026-10-07T14:30:00+00:00",
    "author": "U0AUTHOR",
    "transcript_cutoff": "2026-10-07T13:58:00+00:00",
    "transcript_fingerprint": "fp-1",
    "created_at": "2026-10-07T14:00:00+00:00",
}


def _store(records: RecordStore | None = None) -> RecordStatusUpdateStore:
    return RecordStatusUpdateStore(records if records is not None else InMemoryRecordStore(), TABLE)


def _stored(records: InMemoryRecordStore, sequence: int = 1) -> dict[str, Any] | None:
    result = records.get(TABLE, {"PK": PK, "SK": f"UPDATE#{sequence:06d}"})
    return result.data if result.is_success else None


class _FailingRecordStore(RecordStore):
    """Every operation returns the configured error result; ``calls`` records each operation name."""

    def __init__(self, result: OperationResult[Any]) -> None:
        self._result = result
        self.calls: list[str] = []

    def put(self, table: RecordTable, item: dict[str, Any]) -> OperationResult:
        self.calls.append("put")
        return self._result

    def put_if_not_exists(self, table: RecordTable, item: dict[str, Any]) -> OperationResult:
        self.calls.append("put_if_not_exists")
        return self._result

    def get(self, table: RecordTable, key: dict[str, Any]) -> OperationResult:
        self.calls.append("get")
        return self._result

    def query(self, table: RecordTable, spec: RecordQuery) -> OperationResult:
        self.calls.append("query")
        return self._result

    def delete(self, table: RecordTable, key: dict[str, Any]) -> OperationResult:
        self.calls.append("delete")
        return self._result

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Any = None,
    ) -> OperationResult:
        self.calls.append("update")
        return self._result


def test_the_store_satisfies_the_status_update_store_interface() -> None:
    assert isinstance(_store(), StatusUpdateStore)


def test_the_table_is_keyed_by_the_provisioned_partition_and_sort_attributes() -> None:
    assert (TABLE.name, TABLE.key.partition, TABLE.key.sort) == ("sre_bot_incident_status_updates", "PK", "SK")


def test_append_stores_the_item_layout_the_provisioned_table_holds() -> None:
    records = InMemoryRecordStore()

    result = _store(records).append(DRAFT)

    assert result.is_success and result.data == DRAFT
    assert _stored(records) == DRAFT_ITEM


def test_optional_attributes_are_written_only_when_set() -> None:
    records = InMemoryRecordStore()
    published = replace(PUBLISHED, origin=StatusUpdateOrigin.MODEL)

    _store(records).append(published)

    assert _stored(records) == {
        **DRAFT_ITEM,
        "state": "published",
        "stage": "identified",
        "en": _text_item(published.en),
        "approver": "U0APPROVER",
        "approved_at": "2026-10-07T14:20:00+00:00",
        "published_at": "2026-10-07T14:40:00+00:00",
        "published_by": "U0PUBLISHER",
        "origin": "model",
    }


@pytest.mark.parametrize("origin", [None, *StatusUpdateOrigin])
def test_a_record_reads_back_with_every_field(origin: StatusUpdateOrigin | None) -> None:
    store = _store()
    record = replace(PUBLISHED, origin=origin)
    store.append(record)

    assert store.latest(INCIDENT_ID).data == record


def test_append_at_a_sequence_taken_by_another_record_is_a_conflict() -> None:
    records = InMemoryRecordStore()
    store = _store(records)
    store.append(DRAFT)

    result = store.append(replace(DRAFT, author="U0OTHER"))

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
    assert _stored(records) == DRAFT_ITEM


def test_a_second_append_of_identical_content_is_a_conflict() -> None:
    """Only the writing call's own SDK retry is resolved as created; another call writing the same content lost the race."""
    store = _store()
    store.append(DRAFT)

    result = store.append(DRAFT)

    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT


def test_latest_for_an_incident_without_updates_is_success_with_nothing() -> None:
    result = _store().latest(INCIDENT_ID)

    assert result.is_success and result.data is None


def test_latest_is_the_highest_sequence_of_the_incident() -> None:
    store = _store()
    for sequence in (1, 2, 3):
        store.append(replace(DRAFT, sequence=sequence))
    store.append(replace(DRAFT, incident_id=OTHER_INCIDENT_ID, sequence=9))

    result = store.latest(INCIDENT_ID)

    assert result.data is not None and result.data.sequence == 3


def test_list_is_newest_first_and_scoped_to_the_incident() -> None:
    store = _store()
    for sequence in (2, 1, 10):
        store.append(replace(DRAFT, sequence=sequence))
    store.append(replace(DRAFT, incident_id=OTHER_INCIDENT_ID, sequence=4))

    result = store.list_for_incident(INCIDENT_ID)

    assert result.data is not None and [update.sequence for update in result.data] == [10, 2, 1]


def test_reads_skip_other_items_in_the_incident_partition() -> None:
    """The partition may hold per-incident items that are not updates, under another sort-key prefix."""
    records = InMemoryRecordStore()
    store = _store(records)
    store.append(DRAFT)
    records.put(TABLE, {"PK": PK, "SK": "PERIODIC", "state": "on"})

    assert store.latest(INCIDENT_ID).data == DRAFT
    assert store.list_for_incident(INCIDENT_ID).data == (DRAFT,)


def test_transition_replaces_the_record_while_it_is_in_the_expected_state() -> None:
    store = _store()
    store.append(DRAFT)

    result = store.transition(APPROVED, expected_state=StatusUpdateState.DRAFT)

    assert result.is_success and result.data == APPROVED
    assert store.latest(INCIDENT_ID).data == APPROVED


def test_transition_after_the_state_moved_on_is_a_conflict_and_writes_nothing() -> None:
    store = _store()
    store.append(APPROVED)

    result = store.transition(replace(APPROVED, approver="U0OTHER"), expected_state=StatusUpdateState.DRAFT)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT
    assert store.latest(INCIDENT_ID).data == APPROVED


def test_transition_of_a_missing_record_is_a_conflict() -> None:
    result = _store().transition(APPROVED, expected_state=StatusUpdateState.DRAFT)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT


def test_a_repeated_transition_is_a_conflict() -> None:
    """A write that already landed leaves the guard unmet; the comms callers re-read to recognise their own write."""
    store = _store()
    store.append(DRAFT)
    store.transition(APPROVED, expected_state=StatusUpdateState.DRAFT)

    result = store.transition(APPROVED, expected_state=StatusUpdateState.DRAFT)

    assert result.error_code == ErrorCode.STATUS_UPDATE_CONFLICT


@pytest.mark.parametrize(
    ("record", "expected_state"),
    [
        (DRAFT, StatusUpdateState.APPROVED),
        (PUBLISHED, StatusUpdateState.DRAFT),
        (APPROVED, StatusUpdateState.APPROVED),
    ],
)
def test_an_illegal_transition_raises_before_any_write(record: StatusUpdate, expected_state: StatusUpdateState) -> None:
    records = _FailingRecordStore(OperationResult.success(data=None))

    with pytest.raises(ValueError, match="no status update transition"):
        _store(records).transition(record, expected_state=expected_state)
    assert records.calls == []


def test_publishing_writes_who_published_it() -> None:
    store = _store()
    store.append(APPROVED)

    result = store.transition(PUBLISHED, expected_state=StatusUpdateState.APPROVED)

    assert result.is_success
    assert store.latest(INCIDENT_ID).data == PUBLISHED


def test_marking_not_published_removes_who_published_it() -> None:
    records = InMemoryRecordStore()
    store = _store(records)
    store.append(PUBLISHED)

    result = store.transition(APPROVED, expected_state=StatusUpdateState.PUBLISHED)

    assert result.is_success
    stored = _stored(records)
    assert stored is not None and "published_at" not in stored and "published_by" not in stored
    assert store.latest(INCIDENT_ID).data == APPROVED


def test_a_published_item_without_published_by_reads_as_nobody() -> None:
    records = InMemoryRecordStore()
    store = _store(records)
    store.append(replace(PUBLISHED, published_by=None))

    assert store.latest(INCIDENT_ID).data == replace(PUBLISHED, published_by=None)


@pytest.mark.parametrize(
    "change",
    [
        {"state": "archived"},
        {"sequence": "one"},
        {"next_update_at": "not a time"},
        {"en": {"impact": "only one field"}},
    ],
)
def test_a_malformed_stored_item_is_unreadable(change: dict[str, Any]) -> None:
    records = InMemoryRecordStore()
    records.put(TABLE, {**DRAFT_ITEM, **change})
    store = _store(records)

    for result in (store.latest(INCIDENT_ID), store.list_for_incident(INCIDENT_ID)):
        assert result.status is OperationStatus.PERMANENT_ERROR
        assert result.error_code == ErrorCode.STATUS_UPDATE_UNREADABLE


def test_a_stored_item_missing_an_attribute_is_unreadable() -> None:
    records = InMemoryRecordStore()
    records.put(TABLE, {key: value for key, value in DRAFT_ITEM.items() if key != "author"})

    result = _store(records).latest(INCIDENT_ID)

    assert result.error_code == ErrorCode.STATUS_UPDATE_UNREADABLE


@pytest.mark.parametrize(
    "operation",
    [
        lambda store: store.append(DRAFT),
        lambda store: store.transition(APPROVED, expected_state=StatusUpdateState.DRAFT),
        lambda store: store.latest(INCIDENT_ID),
        lambda store: store.list_for_incident(INCIDENT_ID),
    ],
    ids=["append", "transition", "latest", "list_for_incident"],
)
def test_a_backend_failure_keeps_its_classification_with_a_generic_message(operation: Any) -> None:
    failure = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message=BACKEND_DETAIL, error_code="ThrottlingException", retry_after=3
    )

    result = operation(_store(_FailingRecordStore(failure)))

    assert (result.status, result.error_code, result.retry_after) == (
        OperationStatus.TRANSIENT_ERROR,
        "ThrottlingException",
        3,
    )
    assert result.message and BACKEND_DETAIL not in result.message


@pytest.mark.parametrize(
    "operation",
    [
        lambda store: store.latest(INCIDENT_ID),
        lambda store: store.list_for_incident(INCIDENT_ID),
        lambda store: store.transition(APPROVED, expected_state=StatusUpdateState.DRAFT),
    ],
    ids=["latest", "list_for_incident", "transition"],
)
def test_a_missing_table_is_a_permanent_error_not_an_empty_history_or_a_conflict(operation: Any) -> None:
    missing = OperationResult.error(OperationStatus.NOT_FOUND, message=BACKEND_DETAIL, error_code="ResourceNotFoundException")

    result = operation(_store(_FailingRecordStore(missing)))

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == "ResourceNotFoundException"
