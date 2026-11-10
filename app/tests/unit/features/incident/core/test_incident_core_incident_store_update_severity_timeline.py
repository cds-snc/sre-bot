"""Behavior tests for the severity_changed timeline entry update_fields appends after a severity change.

The entry is appended after the field update, with an id derived from the
incident, the change and its time, so a retry derives the same id. The
recorded and replay cases run on the real store (over InMemoryRecordStore,
reading the timeline table back) and on the fake (reading its timeline); the
append failures run on the real store over a record store whose timeline puts
fail a chosen number of times.
"""

from datetime import timedelta
from typing import Any

import pytest
from structlog.testing import capture_logs

from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import Severity
from features.incident.core.adapters.in_memory import InMemoryIncidentStore, InMemoryTimelineStore
from features.incident.core.adapters.timeline_items import entry_key, severity_entry_id
from features.incident.core.domain import IncidentChanges, SeverityChange, TimelineEntryKind
from features.incident.core.store import IncidentStore, timeline_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import DECLARED_AT, FlakyRecordStore, declared_incident, record_incident_store

pytestmark = pytest.mark.unit

INCIDENT_ID = "inc-1"
BY = "U0EDITOR"
AT = DECLARED_AT + timedelta(hours=1)


def _timeline_items(records: InMemoryRecordStore) -> list[dict[str, Any]]:
    table = timeline_table(get_incident_core_settings().timeline_table)
    result = records.read_all(table, max_items=100)
    assert result.is_success
    return list(result.data or [])


class _Real:
    def __init__(self) -> None:
        self.records = InMemoryRecordStore()
        self.store: IncidentStore = record_incident_store(self.records)

    def entries(self) -> list[dict[str, Any]]:
        return _timeline_items(self.records)


class _Fake:
    def __init__(self) -> None:
        self.timeline = InMemoryTimelineStore()
        self.store: IncidentStore = InMemoryIncidentStore(timeline=self.timeline)

    def entries(self) -> list[dict[str, Any]]:
        return [
            {
                "entry_id": entry.entry_id,
                "kind": entry.kind.value,
                "severity_previous": None if entry.severity_change is None else entry.severity_change.previous,
                "severity_current": None if entry.severity_change is None else entry.severity_change.current,
            }
            for entry in self.timeline.entries(INCIDENT_ID)
        ]


@pytest.fixture(params=["fake", "real"])
async def subject(request: pytest.FixtureRequest) -> _Real | _Fake:
    """A real store or fake holding one created incident, with a way to read its timeline back."""
    built = _Real() if request.param == "real" else _Fake()
    assert (await built.store.create(declared_incident(INCIDENT_ID))).is_success
    return built


async def test_a_severity_change_appends_one_entry_with_a_deterministic_id(subject: _Real | _Fake) -> None:
    """Rated for the first time: one severity_changed entry, unset to SEV2, id derived from the change and time."""
    result = await subject.store.update_fields(INCIDENT_ID, IncidentChanges(severity=Severity.SEV2), by=BY, at=AT)

    assert result.data is not None
    assert result.data.severity is Severity.SEV2
    [entry] = subject.entries()
    change = SeverityChange(previous=None, current=Severity.SEV2)
    assert entry["entry_id"] == severity_entry_id(INCIDENT_ID, change, AT)
    assert entry["kind"] == TimelineEntryKind.SEVERITY_CHANGED.value
    assert entry.get("severity_previous") is None
    assert entry["severity_current"] == Severity.SEV2


async def test_raising_then_clearing_records_each_change(subject: _Real | _Fake) -> None:
    """SEV3 to SEV1 and then cleared: two more entries, each with its own previous and current."""
    assert (await subject.store.update_fields(INCIDENT_ID, IncidentChanges(severity=Severity.SEV3), by=BY, at=AT)).is_success
    assert (await subject.store.update_fields(INCIDENT_ID, IncidentChanges(severity=Severity.SEV1), by=BY, at=AT)).is_success
    assert (await subject.store.update_fields(INCIDENT_ID, IncidentChanges(severity=None), by=BY, at=AT)).is_success

    changes = {(entry.get("severity_previous"), entry.get("severity_current")) for entry in subject.entries()}
    assert changes == {(None, Severity.SEV3), (Severity.SEV3, Severity.SEV1), (Severity.SEV1, None)}


async def test_replaying_the_same_severity_appends_nothing(subject: _Real | _Fake) -> None:
    """The second call finds SEV2 already stored, so neither the field nor the timeline is written."""
    changes = IncidentChanges(severity=Severity.SEV2)
    assert (await subject.store.update_fields(INCIDENT_ID, changes, by=BY, at=AT)).is_success

    assert (await subject.store.update_fields(INCIDENT_ID, changes, by=BY, at=AT + timedelta(minutes=1))).is_success

    assert len(subject.entries()) == 1


async def test_a_change_without_severity_appends_nothing(subject: _Real | _Fake) -> None:
    """Only severity changes are timeline entries in this slice."""
    assert (await subject.store.update_fields(INCIDENT_ID, IncidentChanges(title="Renamed"), by=BY, at=AT)).is_success

    assert subject.entries() == []


async def test_the_entry_item_carries_its_key_author_and_time() -> None:
    """The stored item sits under the incident at '<posted_at>#<entry_id>' and names who changed it."""
    built = _Real()
    assert (await built.store.create(declared_incident(INCIDENT_ID))).is_success

    assert (await built.store.update_fields(INCIDENT_ID, IncidentChanges(severity=Severity.SEV1), by=BY, at=AT)).is_success

    [item] = built.entries()
    entry_id = severity_entry_id(INCIDENT_ID, SeverityChange(previous=None, current=Severity.SEV1), AT)
    assert item["incident_id"] == INCIDENT_ID
    assert item["entry_key"] == entry_key(AT, entry_id)
    assert item["author"] == BY
    assert "text" not in item


async def test_a_transient_append_failure_is_retried_once() -> None:
    """One lost timeline put is retried in the call; the entry lands and the update succeeds."""
    records = FlakyRecordStore(fail_puts={get_incident_core_settings().timeline_table: 1})
    store = record_incident_store(records)
    assert (await store.create(declared_incident(INCIDENT_ID))).is_success

    result = await store.update_fields(INCIDENT_ID, IncidentChanges(severity=Severity.SEV1), by=BY, at=AT)

    assert result.is_success
    assert len(_timeline_items(records)) == 1


async def test_a_failed_append_is_logged_and_never_rolls_the_field_back() -> None:
    """The severity stays changed and the caller gets the updated incident; the lost entry is logged by id."""
    records = FlakyRecordStore(fail_puts={get_incident_core_settings().timeline_table: 2})
    store = record_incident_store(records)
    assert (await store.create(declared_incident(INCIDENT_ID))).is_success

    with capture_logs() as logs:
        result = await store.update_fields(INCIDENT_ID, IncidentChanges(severity=Severity.SEV1), by=BY, at=AT)

    assert result.data is not None
    assert result.data.severity is Severity.SEV1
    assert _timeline_items(records) == []
    failed = [log for log in logs if log["event"] == "incident_timeline_entry_failed"]
    entry_id = severity_entry_id(INCIDENT_ID, SeverityChange(previous=None, current=Severity.SEV1), AT)
    assert [(log["incident_id"], log["entry_id"]) for log in failed] == [(INCIDENT_ID, entry_id)]
