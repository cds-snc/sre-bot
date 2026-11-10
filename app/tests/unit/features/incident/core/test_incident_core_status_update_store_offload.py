"""Behavior tests for where RecordStatusUpdateStore runs its RecordStore work.

The store is awaited from the event loop; each call runs its blocking
RecordStore requests in a worker thread. A recording RecordStore (the in-memory
store with every request noting its thread) shows which thread ran the request;
a failing RecordStore stub checks the classified result still comes back
through the thread.
"""

import threading
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from structlog.testing import capture_logs

from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import RecordStore
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
)
from features.incident.core.store import RecordStatusUpdateStore, status_updates_table
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

TABLE = status_updates_table("sre_bot_incident_status_updates")
INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"
TEXT = StatusUpdateText(affected_service="GC Notify", impact="Delayed.", current_action="Restarting.", workaround="")
DRAFT = StatusUpdate(
    incident_id=INCIDENT_ID,
    sequence=1,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.INVESTIGATING,
    en=TEXT,
    fr=TEXT,
    next_update_at=datetime(2026, 10, 7, 14, 30, tzinfo=UTC),
    author="U0AUTHOR",
    transcript_cutoff=datetime(2026, 10, 7, 13, 58, tzinfo=UTC),
    transcript_fingerprint="fp-1",
    created_at=datetime(2026, 10, 7, 14, 0, tzinfo=UTC),
)


class _ThreadRecordingStore(InMemoryRecordStore):
    """The in-memory RecordStore, noting the thread of every request it serves."""

    def __init__(self) -> None:
        super().__init__()
        self.threads: list[int] = []

    def query(self, *args: Any, **kwargs: Any) -> OperationResult:
        self.threads.append(threading.get_ident())
        return super().query(*args, **kwargs)

    def put_if_not_exists(self, *args: Any, **kwargs: Any) -> OperationResult:
        self.threads.append(threading.get_ident())
        return super().put_if_not_exists(*args, **kwargs)


async def test_an_append_and_a_read_run_their_record_requests_off_the_event_loop_thread() -> None:
    records = _ThreadRecordingStore()
    store = RecordStatusUpdateStore(records, TABLE)

    appended = await store.append(DRAFT)
    listed = await store.list_for_incident(INCIDENT_ID)

    assert appended.is_success
    assert list(listed.data or []) == [DRAFT]
    assert len(records.threads) >= 2
    assert threading.get_ident() not in records.threads


async def test_a_record_failure_comes_back_through_the_thread_as_the_classified_result() -> None:
    records = MagicMock(spec=RecordStore)
    records.query.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="backend detail", error_code="ServiceUnavailable", retry_after=2
    )
    store = RecordStatusUpdateStore(records, TABLE)

    with capture_logs():
        result = await store.latest(INCIDENT_ID)

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert "backend detail" not in (result.message or "")
