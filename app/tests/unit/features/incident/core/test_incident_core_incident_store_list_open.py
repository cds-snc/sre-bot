"""Behavior tests for IncidentStore.list_open.

The real store runs over InMemoryRecordStore. The open index is sparse: only
items carrying open_bucket are in it, and they come back oldest first by
opened_at, the fixed-width text time the writers set.
"""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import RecordStore
from features.incident.core.store import OPEN_BUCKET, RecordIncidentStore, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

TABLE = incidents_table("incidents")


def _item(incident_id: str, *, opened_at: str | None = None, **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": incident_id,
        "record_version": Decimal(1),
        "title": f"Incident {incident_id}",
        "status": "Open",
        "declared_by": "U0DECLARER",
        "declared_at": "2026-10-15T14:00:00.000000+00:00",
        "security_incident": False,
    }
    if opened_at is not None:
        item.update(open_bucket=OPEN_BUCKET, opened_at=opened_at)
    item.update(overrides)
    return {key: value for key, value in item.items() if value is not None}


def _store(*items: dict[str, Any]) -> RecordIncidentStore:
    records = InMemoryRecordStore()
    for item in items:
        assert records.put(TABLE, item).is_success
    return RecordIncidentStore(records, TABLE)


def test_only_open_incidents_come_back_oldest_first() -> None:
    store = _store(
        _item("late", opened_at="2026-10-15T16:00:00.000000+00:00"),
        _item("closed", status="Closed"),
        _item("early", opened_at="2026-10-15T09:00:00.000000+00:00"),
    )

    result = store.list_open()

    assert result.is_success
    assert result.data is not None
    assert [incident.id for incident in result.data] == ["early", "late"]


def test_no_open_incident_is_an_empty_list() -> None:
    result = _store(_item("closed", status="Closed")).list_open()

    assert result.is_success
    assert result.data is not None
    assert list(result.data) == []


def test_an_open_item_without_record_version_makes_the_list_unreadable() -> None:
    """A partial list would hide an open incident, so the read refuses."""
    store = _store(
        _item("ok", opened_at="2026-10-15T09:00:00.000000+00:00"),
        _item("legacy", opened_at="2026-10-15T10:00:00.000000+00:00", record_version=None),
    )

    result = store.list_open()

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE


def test_a_store_failure_is_classified() -> None:
    records = MagicMock(spec=RecordStore)
    records.query.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="timeout talking to dynamodb", error_code="TIMEOUT"
    )

    result = RecordIncidentStore(records, TABLE).list_open()

    assert (result.status, result.error_code) == (OperationStatus.TRANSIENT_ERROR, "TIMEOUT")
    assert result.message is not None
    assert "dynamodb" not in result.message
