"""Behavior tests for IncidentStore.set_status: the status and the open-index bucket rules.

Closing removes the incident from the open list; reopening puts it back with
the reopen time as its opened time; a move between open statuses changes the
status only. The list-level cases run on the real store over InMemoryRecordStore
and on the fake; the stored open_bucket and opened_at are read on the real
store's table.
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.adapters.incident_items import OPEN_BUCKET, format_stored_time
from features.incident.core.store import IncidentStore, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import DECLARED_AT, CountingRecordStore, declared_incident, record_incident_store

pytestmark = pytest.mark.unit

INCIDENT_ID = "inc-1"
AT = DECLARED_AT + timedelta(days=1)


def _real() -> IncidentStore:
    return record_incident_store(InMemoryRecordStore())


STORES: dict[str, Callable[[], IncidentStore]] = {"real": _real, "fake": InMemoryIncidentStore}


@pytest.fixture(params=sorted(STORES))
def store(request: pytest.FixtureRequest) -> IncidentStore:
    """A real store or fake holding one created, open incident."""
    created = STORES[request.param]()
    assert created.create(declared_incident(INCIDENT_ID)).is_success
    return created


def _open_ids(store: IncidentStore) -> set[str]:
    listed = store.list_open().data
    assert listed is not None
    return {incident.id for incident in listed}


def test_moving_between_open_statuses_keeps_the_incident_listed(store: IncidentStore) -> None:
    """In Progress is still open."""
    result = store.set_status(INCIDENT_ID, IncidentStatus.IN_PROGRESS, at=AT)

    assert result.data is not None
    assert result.data.status is IncidentStatus.IN_PROGRESS
    assert _open_ids(store) == {INCIDENT_ID}


def test_closing_leaves_the_open_list(store: IncidentStore) -> None:
    """Closed is the only status that is not open."""
    result = store.set_status(INCIDENT_ID, IncidentStatus.CLOSED, at=AT)

    assert result.data is not None
    assert result.data.status is IncidentStatus.CLOSED
    assert _open_ids(store) == set()


def test_reopening_returns_to_the_open_list(store: IncidentStore) -> None:
    """A closed incident set back to an open status is listed again."""
    assert store.set_status(INCIDENT_ID, IncidentStatus.CLOSED, at=AT).is_success

    result = store.set_status(INCIDENT_ID, IncidentStatus.OPEN, at=AT + timedelta(hours=1))

    assert result.data is not None
    assert result.data.status is IncidentStatus.OPEN
    assert _open_ids(store) == {INCIDENT_ID}


def test_the_stored_bucket_follows_close_and_reopen() -> None:
    """Close removes open_bucket and opened_at; reopen sets them, opened_at being the reopen time; open to open keeps them."""
    records = InMemoryRecordStore()
    store = record_incident_store(records)
    assert store.create(declared_incident(INCIDENT_ID)).is_success
    table = incidents_table(get_incident_core_settings().incidents_table)

    def item() -> dict[str, Any]:
        return records.get(table, {"id": INCIDENT_ID}).data or {}

    assert store.set_status(INCIDENT_ID, IncidentStatus.IN_PROGRESS, at=AT).is_success
    assert (item()["open_bucket"], item()["opened_at"]) == (OPEN_BUCKET, format_stored_time(DECLARED_AT))
    assert store.set_status(INCIDENT_ID, IncidentStatus.CLOSED, at=AT).is_success
    assert "open_bucket" not in item() and "opened_at" not in item()
    reopened_at = AT + timedelta(hours=1)
    assert store.set_status(INCIDENT_ID, IncidentStatus.READY_TO_BE_REVIEWED, at=reopened_at).is_success
    assert (item()["open_bucket"], item()["opened_at"]) == (OPEN_BUCKET, format_stored_time(reopened_at))


def test_setting_the_stored_status_again_writes_nothing() -> None:
    """A replay of the same status is a no-op: no update is sent."""
    records = CountingRecordStore()
    store = record_incident_store(records)
    assert store.create(declared_incident(INCIDENT_ID)).is_success
    assert store.set_status(INCIDENT_ID, IncidentStatus.CLOSED, at=AT).is_success
    writes = list(records.writes)

    result = store.set_status(INCIDENT_ID, IncidentStatus.CLOSED, at=AT)

    assert result.is_success
    assert records.writes == writes


def test_a_missing_incident_is_not_an_incident(store: IncidentStore) -> None:
    """An unknown id is NOT_FOUND."""
    result = store.set_status("inc-missing", IncidentStatus.CLOSED, at=AT)

    assert (result.status, result.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_AN_INCIDENT)


def test_a_naive_time_raises(store: IncidentStore) -> None:
    """The reopen time is stored and sorted as text, so it must carry its zone."""
    with pytest.raises(ValueError, match="timezone"):
        store.set_status(INCIDENT_ID, IncidentStatus.CLOSED, at=AT.replace(tzinfo=None))
