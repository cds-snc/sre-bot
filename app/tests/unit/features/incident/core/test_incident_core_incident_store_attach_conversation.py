"""Behavior tests for IncidentStore.attach_conversation: binding a chat conversation to a created incident.

The record is read first, so a missing incident, a record of another version
or one already naming another conversation is refused before anything is
written. Then the binding is put, and a primary binding's conversation is
copied into the record (conversation map and channel_id) by one update
guarded on record_version and on no conversation being stored. The cases
without failure injection run against the real store over InMemoryRecordStore
and the in-memory fake, which must agree. Write order, store failures, the
guard and the legacy case run on the real store over FlakyRecordStore, which
fails a chosen table's puts or updates and records every write by table.
"""

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import ExpectedValue, RecordChange, RecordTable, SetAttribute
from features.incident.common.settings import get_incident_core_settings
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.adapters.incident_items import RECORD_VERSION
from features.incident.core.domain import IncidentBinding
from features.incident.core.store import IncidentStore, bindings_table, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import (
    DECLARED_AT,
    FlakyRecordStore,
    binding_on,
    declared_incident,
    record_incident_store,
    seed_legacy_incident,
    slack_conversation,
)

pytestmark = pytest.mark.unit

CHANNEL = "C0INCIDENT"
OTHER_CHANNEL = "C0OTHER"
INCIDENT_ID = "inc-1"


def _incidents() -> RecordTable:
    return incidents_table(get_incident_core_settings().incidents_table)


def _bindings() -> RecordTable:
    return bindings_table(get_incident_core_settings().bindings_table)


def _real() -> IncidentStore:
    return record_incident_store(InMemoryRecordStore())


STORES: dict[str, Callable[[], IncidentStore]] = {"real": _real, "fake": InMemoryIncidentStore}


@pytest.fixture(params=sorted(STORES))
def store(request: pytest.FixtureRequest) -> IncidentStore:
    """A real store or fake holding one created incident with no surface."""
    created = STORES[request.param]()
    assert created.create(declared_incident(INCIDENT_ID)).is_success
    return created


def _created(records: InMemoryRecordStore) -> IncidentStore:
    store = record_incident_store(records)
    assert store.create(declared_incident(INCIDENT_ID)).is_success
    return store


def _record(records: InMemoryRecordStore) -> dict[str, Any]:
    return records.get(_incidents(), {"id": INCIDENT_ID}).data or {}


def test_a_primary_attach_makes_the_conversation_the_incidents(store: IncidentStore) -> None:
    """The answer, a later read and the conversation lookup all carry the attached conversation."""
    expected = dataclasses.replace(declared_incident(INCIDENT_ID), conversation=slack_conversation(CHANNEL))

    result = store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID))

    assert result.is_success
    assert result.data == expected
    assert store.get(INCIDENT_ID).data == expected
    assert store.find_by_conversation(slack_conversation(CHANNEL)).data == expected


def test_attaching_the_same_conversation_again_is_a_no_op(store: IncidentStore) -> None:
    """A retry or a replay answers the same incident."""
    first = store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID))

    second = store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID))

    assert second.is_success
    assert second.data == first.data


def test_another_conversation_on_the_record_is_a_conflict_and_nothing_moves(store: IncidentStore) -> None:
    """Moving the primary conversation is recreate's job; the new channel is not bound."""
    assert store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID)).is_success

    result = store.attach_conversation(INCIDENT_ID, binding_on(OTHER_CHANNEL, INCIDENT_ID))

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INCIDENT_RECORD_CONFLICT)
    assert store.get(INCIDENT_ID).data == dataclasses.replace(
        declared_incident(INCIDENT_ID), conversation=slack_conversation(CHANNEL)
    )
    lookup = store.find_by_conversation(slack_conversation(OTHER_CHANNEL))
    assert lookup.error_code == ErrorCode.NOT_AN_INCIDENT


def test_a_missing_incident_is_not_an_incident(store: IncidentStore) -> None:
    """No binding is left for an incident that does not exist."""
    result = store.attach_conversation("inc-missing", binding_on(CHANNEL, "inc-missing"))

    assert (result.status, result.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)
    assert store.find_by_conversation(slack_conversation(CHANNEL)).error_code == ErrorCode.NOT_AN_INCIDENT


def test_a_secondary_conversation_is_bound_without_changing_the_record(store: IncidentStore) -> None:
    """A non-primary binding is another way in; the record's conversation copy stays the primary's."""
    assert store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID)).is_success

    result = store.attach_conversation(INCIDENT_ID, binding_on(OTHER_CHANNEL, INCIDENT_ID, primary=False))

    assert result.is_success
    assert result.data is not None
    assert result.data.conversation == slack_conversation(CHANNEL)
    assert store.find_by_conversation(slack_conversation(OTHER_CHANNEL)).data == result.data


def test_the_same_channel_under_another_tenant_is_not_matched(store: IncidentStore) -> None:
    """The conversation is matched with its system and tenant."""
    assert store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID)).is_success

    lookup = store.find_by_conversation(slack_conversation(CHANNEL, tenant="T0OTHER"))

    assert (lookup.status, lookup.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)


@pytest.mark.parametrize(
    ("binding", "message"),
    [
        (binding_on(CHANNEL, "inc-other"), "incident_id"),
        (binding_on(CHANNEL, INCIDENT_ID, archived_at=DECLARED_AT), "archived"),
    ],
    ids=["other-incident", "archived"],
)
def test_a_caller_error_raises_and_writes_nothing(store: IncidentStore, binding: IncidentBinding, message: str) -> None:
    """Only an active binding of this incident can be attached."""
    with pytest.raises(ValueError, match=message):
        store.attach_conversation(INCIDENT_ID, binding)

    assert store.find_by_conversation(slack_conversation(CHANNEL)).error_code == ErrorCode.NOT_AN_INCIDENT


def test_the_binding_is_written_before_the_record_copy() -> None:
    """The lookup reads bindings first, so the binding lands before the record names the conversation."""
    records = FlakyRecordStore()
    store = _created(records)
    records.writes.clear()

    assert store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID)).is_success

    assert records.writes == [(_bindings().name, "put_if_not_exists"), (_incidents().name, "update")]
    assert _record(records)["conversation"] == {"system": "slack", "tenant": "T0SLACK", "vendor_id": CHANNEL}
    assert _record(records)["channel_id"] == CHANNEL


def test_a_failed_binding_write_leaves_the_record_unchanged() -> None:
    """No record copy is written without its binding; the error is classified with a generic message."""
    records = FlakyRecordStore({_bindings().name: 1})
    store = _created(records)
    records.writes.clear()

    result = store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID))

    assert (result.status, result.error_code) == (OperationStatus.TRANSIENT_ERROR, "ServiceUnavailable")
    assert result.message == "The incident store is unavailable."
    assert records.writes == [(_bindings().name, "put_if_not_exists")]
    assert "conversation" not in _record(records)


def test_a_failed_record_copy_leaves_a_live_binding_and_a_retry_completes_it() -> None:
    """Between the steps the lookup already finds the incident through its binding; the retry writes the copy."""
    records = FlakyRecordStore(fail_updates={_incidents().name: 1})
    store = _created(records)

    failed = store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID))

    assert failed.status is OperationStatus.TRANSIENT_ERROR
    assert store.find_by_conversation(slack_conversation(CHANNEL)).data == declared_incident(INCIDENT_ID)
    assert store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID)).is_success
    assert _record(records)["channel_id"] == CHANNEL


class GuardSpy(InMemoryRecordStore):
    """InMemoryRecordStore that keeps every update's guard, and can store a conversation just before the next update."""

    def __init__(self) -> None:
        super().__init__()
        self.guards: list[Mapping[str, ExpectedValue] | None] = []
        self.race_with: str | None = None

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Mapping[str, ExpectedValue] | None = None,
    ) -> OperationResult:
        self.guards.append(expected)
        if self.race_with is not None:
            channel, self.race_with = self.race_with, None
            conversation = {"system": "slack", "tenant": "T0SLACK", "vendor_id": channel}
            super().update(table, key, [SetAttribute("conversation", conversation), SetAttribute("channel_id", channel)])
        return super().update(table, key, changes, expected=expected)


def test_the_copy_is_guarded_on_the_version_and_no_stored_conversation() -> None:
    """Only an end-state record without a conversation receives the copy."""
    records = GuardSpy()
    store = _created(records)

    assert store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID)).is_success

    assert records.guards == [{"record_version": RECORD_VERSION, "conversation": None}]


def test_a_concurrent_attach_of_another_conversation_is_a_conflict() -> None:
    """When another writer stores a conversation between the read and the update, the guard fails and the re-read decides."""
    records = GuardSpy()
    store = _created(records)
    records.race_with = OTHER_CHANNEL

    result = store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID))

    assert result.error_code == ErrorCode.INCIDENT_RECORD_CONFLICT
    assert _record(records)["channel_id"] == OTHER_CHANNEL


def test_a_concurrent_attach_of_the_same_conversation_succeeds() -> None:
    """The guard fails on a copy that already holds this conversation, which the re-read accepts."""
    records = GuardSpy()
    store = _created(records)
    records.race_with = CHANNEL

    result = store.attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID))

    assert result.is_success
    assert result.data is not None
    assert result.data.conversation == slack_conversation(CHANNEL)


def test_a_legacy_item_is_a_conflict_and_nothing_is_written() -> None:
    """A legacy item is raised by the upgrade job, never patched by attach."""
    records = FlakyRecordStore()
    seed_legacy_incident(records, CHANNEL, incident_id=INCIDENT_ID)
    records.writes.clear()

    result = record_incident_store(records).attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID))

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INCIDENT_RECORD_CONFLICT)
    assert records.writes == []


def test_a_failed_record_read_is_classified_and_nothing_is_written() -> None:
    """A store that cannot be read is a classified failure, never a missing incident."""

    class Unreadable(FlakyRecordStore):
        def get(self, table: RecordTable, key: dict[str, Any]) -> OperationResult:
            return OperationResult.error(OperationStatus.TRANSIENT_ERROR, message="throttled", error_code="Throttling")

    records = Unreadable()

    result = record_incident_store(records).attach_conversation(INCIDENT_ID, binding_on(CHANNEL, INCIDENT_ID))

    assert (result.status, result.error_code) == (OperationStatus.TRANSIENT_ERROR, "Throttling")
    assert records.writes == []
