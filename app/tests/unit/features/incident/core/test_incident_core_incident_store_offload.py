"""Behavior tests for where RecordIncidentStore runs its RecordStore work.

The store is awaited from the event loop; each call runs its blocking
RecordStore requests in a worker thread. A recording RecordStore (the in-memory
store with every request noting its thread) shows which thread ran the request,
and structlog's capture shows that context bound before the await reaches the
adapter's log lines. A failing RecordStore stub checks the classified result
still comes back through the thread.
"""

import threading
from typing import Any
from unittest.mock import MagicMock

import pytest
import structlog
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import RecordStore
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import declared_incident, record_incident_store, slack_conversation

pytestmark = pytest.mark.unit

INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"


class _ThreadRecordingStore(InMemoryRecordStore):
    """The in-memory RecordStore, noting the thread of every request it serves."""

    def __init__(self) -> None:
        super().__init__()
        self.threads: list[int] = []

    def get(self, *args: Any, **kwargs: Any) -> OperationResult:
        self.threads.append(threading.get_ident())
        return super().get(*args, **kwargs)

    def query(self, *args: Any, **kwargs: Any) -> OperationResult:
        self.threads.append(threading.get_ident())
        return super().query(*args, **kwargs)

    def put_if_not_exists(self, *args: Any, **kwargs: Any) -> OperationResult:
        self.threads.append(threading.get_ident())
        return super().put_if_not_exists(*args, **kwargs)

    def update(self, *args: Any, **kwargs: Any) -> OperationResult:
        self.threads.append(threading.get_ident())
        return super().update(*args, **kwargs)


async def test_a_read_runs_its_record_request_off_the_event_loop_thread() -> None:
    records = _ThreadRecordingStore()
    store = record_incident_store(records)
    assert (await store.create(declared_incident(INCIDENT_ID))).is_success
    records.threads.clear()

    result = await store.get(INCIDENT_ID)

    assert result.is_success
    assert records.threads
    assert threading.get_ident() not in records.threads


async def test_a_lookup_by_conversation_runs_every_record_request_off_the_event_loop_thread() -> None:
    """The bindings read and the by-channel fallback are one call; neither request runs on the loop."""
    records = _ThreadRecordingStore()
    store = record_incident_store(records)

    result = await store.find_by_conversation(slack_conversation("C0NOINCIDENT"))

    assert result.error_code == ErrorCode.NOT_AN_INCIDENT
    assert len(records.threads) >= 2
    assert threading.get_ident() not in records.threads


async def test_a_guarded_write_runs_its_record_requests_off_the_event_loop_thread() -> None:
    records = _ThreadRecordingStore()
    store = record_incident_store(records)
    assert (await store.create(declared_incident(INCIDENT_ID))).is_success
    records.threads.clear()

    result = await store.set_status(INCIDENT_ID, IncidentStatus.CLOSED, at=declared_incident(INCIDENT_ID).declared_at)

    assert result.is_success
    assert records.threads
    assert threading.get_ident() not in records.threads


async def test_context_bound_before_the_await_is_visible_inside_the_worker_thread() -> None:
    """structlog's contextvars are what the adapter's log lines merge, so the thread must see them."""
    seen: list[dict[str, Any]] = []

    def _read_context(*_: Any, **__: Any) -> OperationResult:
        seen.append(structlog.contextvars.get_contextvars())
        return OperationResult.success(data=None)

    records = MagicMock(spec=RecordStore)
    records.get.side_effect = _read_context
    store = record_incident_store(records)

    with structlog.contextvars.bound_contextvars(request_id="req-1"):
        await store.get(INCIDENT_ID)

    assert seen == [{"request_id": "req-1"}]


async def test_a_record_failure_comes_back_through_the_thread_as_the_classified_result() -> None:
    records = MagicMock(spec=RecordStore)
    records.get.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="backend detail", error_code="ServiceUnavailable", retry_after=2
    )
    store = record_incident_store(records)

    with capture_logs():
        result = await store.get(INCIDENT_ID)

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert "backend detail" not in (result.message or "")


async def test_the_fake_answers_on_the_event_loop_without_a_thread() -> None:
    """The in-memory fake has no blocking work, so it is a plain coroutine."""
    store = InMemoryIncidentStore()
    store.seed(declared_incident(INCIDENT_ID))

    result = await store.get(INCIDENT_ID)

    assert result.is_success
