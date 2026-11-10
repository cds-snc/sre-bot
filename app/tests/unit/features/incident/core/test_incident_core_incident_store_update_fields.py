"""Behavior tests for IncidentStore.update_fields: the guarded field update of an end-state record.

Success, replay, the missing incident and the caller errors run on the real
store over InMemoryRecordStore and on the in-memory fake, which must agree. The
guard and the lost-guard retry run on the real store only: GuardSpy keeps every
update's guard, and LosingRecordStore lets another writer change the item just
before the store's next update lands, as a concurrent writer would.
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import ExpectedValue, RecordChange, RecordStore, RecordTable, SetAttribute
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import Severity
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.adapters.incident_items import RECORD_VERSION
from features.incident.core.domain import IncidentChanges
from features.incident.core.store import IncidentStore, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import DECLARED_AT, declared_incident, record_incident_store

pytestmark = pytest.mark.unit

INCIDENT_ID = "inc-1"
BY = "U0EDITOR"
AT = DECLARED_AT + timedelta(hours=1)
DETECTED = datetime(2026, 10, 1, 11, 30, tzinfo=UTC)


class GuardSpy(InMemoryRecordStore):
    """InMemoryRecordStore that keeps the changes and guard of every update."""

    def __init__(self) -> None:
        super().__init__()
        self.updates: list[tuple[Sequence[RecordChange], Mapping[str, ExpectedValue] | None]] = []

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Mapping[str, ExpectedValue] | None = None,
    ) -> OperationResult:
        self.updates.append((changes, expected))
        return super().update(table, key, changes, expected=expected)


class LosingRecordStore(InMemoryRecordStore):
    """InMemoryRecordStore where another writer sets ``title`` on the incidents table before each of the next ``losses`` updates."""

    def __init__(self, losses: int) -> None:
        super().__init__()
        self.losses = losses
        self.attempts = 0

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Mapping[str, ExpectedValue] | None = None,
    ) -> OperationResult:
        if table.name == _incidents().name and expected is not None:
            self.attempts += 1
            if self.losses > 0:
                self.losses -= 1
                super().update(table, key, [SetAttribute("title", f"Renamed by another writer {self.attempts}")])
        return super().update(table, key, changes, expected=expected)


def _incidents() -> RecordTable:
    return incidents_table(get_incident_core_settings().incidents_table)


def _real() -> IncidentStore:
    return record_incident_store(InMemoryRecordStore())


STORES: dict[str, Callable[[], IncidentStore]] = {"real": _real, "fake": InMemoryIncidentStore}


@pytest.fixture(params=sorted(STORES))
def store(request: pytest.FixtureRequest) -> IncidentStore:
    """A real store or fake holding one created incident."""
    created = STORES[request.param]()
    assert created.create(declared_incident(INCIDENT_ID)).is_success
    return created


def test_the_named_fields_change_and_the_others_stay(store: IncidentStore) -> None:
    """Only the fields the change names are written; the answer equals a later read."""
    result = store.update_fields(
        INCIDENT_ID, IncidentChanges(title="Database failover", detected_at=DETECTED, security_incident=True), by=BY, at=AT
    )

    assert result.data is not None
    assert (result.data.title, result.data.detected_at, result.data.security_incident) == ("Database failover", DETECTED, True)
    assert result.data.declared_by == "U0DECLARER"
    assert store.get(INCIDENT_ID).data == result.data


def test_a_time_is_cleared_with_none(store: IncidentStore) -> None:
    """None clears an optional field; KEEP leaves it as stored."""
    assert store.update_fields(INCIDENT_ID, IncidentChanges(impact_ended_at=AT), by=BY, at=AT).is_success

    result = store.update_fields(INCIDENT_ID, IncidentChanges(impact_ended_at=None), by=BY, at=AT)

    assert result.data is not None
    assert result.data.impact_ended_at is None


def test_replaying_the_same_change_writes_nothing() -> None:
    """A repeated change finds the values already stored, so no update is sent."""
    records = GuardSpy()
    store = record_incident_store(records)
    assert store.create(declared_incident(INCIDENT_ID)).is_success
    changes = IncidentChanges(title="Database failover")
    first = store.update_fields(INCIDENT_ID, changes, by=BY, at=AT)

    second = store.update_fields(INCIDENT_ID, changes, by=BY, at=AT)

    assert second.is_success
    assert second.data == first.data
    assert len(records.updates) == 1


def test_the_update_is_guarded_on_the_version_and_the_changed_attributes_read_values() -> None:
    """A concurrent change to the same attribute, or a version change, makes the write miss rather than overwrite."""
    records = GuardSpy()
    store = record_incident_store(records)
    assert store.create(declared_incident(INCIDENT_ID)).is_success

    assert store.update_fields(
        INCIDENT_ID, IncidentChanges(title="Database failover", severity=Severity.SEV2), by=BY, at=AT
    ).is_success

    changes, expected = records.updates[0]
    assert {change.attribute for change in changes} == {"title", "severity"}
    assert expected == {"record_version": RECORD_VERSION, "title": f"Incident {INCIDENT_ID}", "severity": None}


def test_a_lost_guard_is_read_again_and_retried_once() -> None:
    """Another writer's change lands first; the store re-reads, recomputes and writes on the new values."""
    records = LosingRecordStore(losses=1)
    store = record_incident_store(records)
    assert store.create(declared_incident(INCIDENT_ID)).is_success

    result = store.update_fields(INCIDENT_ID, IncidentChanges(title="Database failover"), by=BY, at=AT)

    assert result.data is not None
    assert result.data.title == "Database failover"
    assert records.attempts == 2


def test_a_guard_lost_twice_is_a_conflict_and_the_other_writer_wins() -> None:
    """After one retry the store stops; the caller gets INCIDENT_RECORD_CONFLICT and the record keeps the other write."""
    records = LosingRecordStore(losses=2)
    store = record_incident_store(records)
    assert store.create(declared_incident(INCIDENT_ID)).is_success

    result = store.update_fields(INCIDENT_ID, IncidentChanges(title="Database failover"), by=BY, at=AT)

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INCIDENT_RECORD_CONFLICT)
    stored = store.get(INCIDENT_ID).data
    assert stored is not None
    assert stored.title == "Renamed by another writer 2"


def test_a_missing_incident_is_not_an_incident(store: IncidentStore) -> None:
    """An unknown id is NOT_FOUND, nothing is written."""
    result = store.update_fields("inc-missing", IncidentChanges(title="x"), by=BY, at=AT)

    assert (result.status, result.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)


def test_a_store_failure_is_classified_with_a_generic_message() -> None:
    """The backend's status, code and retry hint are kept; its message is not."""
    records = MagicMock(spec=RecordStore)
    records.get.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="throttled: arn:aws:...", error_code="Throttling", retry_after=3
    )

    result = record_incident_store(records).update_fields(INCIDENT_ID, IncidentChanges(title="x"), by=BY, at=AT)

    assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "Throttling", 3)
    assert result.message == "The incident store is unavailable."


@pytest.mark.parametrize(
    ("build", "match"),
    [
        (lambda: IncidentChanges(), "at least one"),
        (lambda: IncidentChanges(title="  "), "title"),
        (lambda: IncidentChanges(detected_at=datetime(2026, 10, 1, 11, 30)), "detected_at"),
        (lambda: IncidentChanges(severity=2), "severity"),  # type: ignore[arg-type]
        (lambda: IncidentChanges(security_incident=None), "security_incident"),  # type: ignore[arg-type]
    ],
    ids=["nothing", "blank-title", "naive-time", "bare-int-severity", "cleared-flag"],
)
def test_a_change_the_record_cannot_hold_raises(build: Callable[[], IncidentChanges], match: str) -> None:
    """Caller errors are refused when the change is built, before any read or write."""
    with pytest.raises(ValueError, match=match):
        build()
