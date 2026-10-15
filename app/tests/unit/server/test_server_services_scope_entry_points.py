"""Reference feature entry points that open a service scope from the host opener.

A feature-style Slack listener and a feature-style background job each obtain
the host's ServiceScopeOpener from their registration point (registrar.service_scopes,
registry.service_scopes), open one scope per invocation, resolve the RecordStore
contract, build a small service from it through a provider function, call one
service method, and let the scope close. The service is built from the resolved
contract and never receives the resolver.

The host opener runs over the service_registry fixture. RecordStore is
re-registered there as a generator factory that yields a MagicMock fake and
records its cleanup, so the scope's close is observable. A failure inside the
scope must still close it, and the exception must reach the caller.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

import pytest
import svcs

from contracts.operations import OperationResult
from contracts.records import KeySchema, RecordStore, RecordTable
from contracts.scheduler.registry import BackgroundJobRegistry
from contracts.services import ServiceScopeOpener
from contracts.slack.registrar import SlackCommandRegistrar
from server.services import SvcsServiceScopeOpener
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit

_TABLE = RecordTable(name="reference_records", key=KeySchema(partition="pk"))
_ACTION_ID = "reference.lookup.fetch"
_JOB_NAME = "reference_lookup_daily"


class _LookupFailedError(Exception):
    """Raised by the fake store to model a failure inside the scope."""


class _RecordLookup:
    """Feature service built from the resolved RecordStore; it never sees the resolver."""

    def __init__(self, store: RecordStore) -> None:
        self._store = store

    def fetch(self, key: dict[str, Any]) -> OperationResult[Any]:
        return self._store.get(_TABLE, key)


def build_record_lookup(store: RecordStore) -> _RecordLookup:
    """Provider function: takes the resolved contract as an argument and returns the service."""
    return _RecordLookup(store)


def register(registrar: SlackCommandRegistrar) -> None:
    """Feature registration: the listener resolves its scope on each invocation, not at registration."""

    def handle_fetch(ack: Callable[[], object], body: dict[str, Any]) -> OperationResult[Any]:
        ack()
        with registrar.service_scopes.create_scope() as resolver:
            return build_record_lookup(resolver.get(RecordStore)).fetch(body["key"])

    registrar.register_block_action(_ACTION_ID, handle_fetch)


class _RecordingJobRegistry:
    """Stores each registered job by name so a test can invoke it as the scheduler would."""

    def __init__(self, service_scopes: ServiceScopeOpener) -> None:
        self._service_scopes = service_scopes
        self.jobs: dict[str, Callable[[], None]] = {}

    @property
    def service_scopes(self) -> ServiceScopeOpener:
        return self._service_scopes

    def register_daily(self, *, job_name: str, schedule: str, job: Callable[[], None]) -> None:
        self.jobs[job_name] = job

    def register_interval(self, *, job_name: str, every: Any, job: Callable[[], None]) -> None:
        self.jobs[job_name] = job


def register_job(registry: BackgroundJobRegistry) -> None:
    """Feature job registration: the job opens its scope from the registry's opener when it runs."""

    def run_lookup() -> None:
        with registry.service_scopes.create_scope() as resolver:
            build_record_lookup(resolver.get(RecordStore)).fetch({"pk": "INC-1"})

    registry.register_daily(job_name=_JOB_NAME, schedule="03:30", job=run_lookup)


@dataclass
class _StoreTracking:
    """The fake RecordStore the fixture yields, and the list of its cleanups."""

    store: MagicMock = field(default_factory=lambda: MagicMock(spec=RecordStore))
    closed: list[MagicMock] = field(default_factory=list)


@pytest.fixture
async def tracked_record_store(service_registry: svcs.Registry) -> _StoreTracking:
    """Re-register RecordStore as a generator factory yielding one fake and recording its cleanup."""
    tracking = _StoreTracking()

    def tracked_store() -> Iterator[RecordStore]:
        yield tracking.store
        tracking.closed.append(tracking.store)

    service_registry.register_factory(RecordStore, tracked_store)
    return tracking


async def test_slack_listener_resolves_the_record_store_through_the_host_opener(
    service_registry: svcs.Registry, tracked_record_store: _StoreTracking
) -> None:
    """A listener opens a scope from the registrar, resolves RecordStore, and gets the service's result.

    Stub strategy: FakeSlackRegistrar is given the host opener over the fixture
    registry; the fake store returns a canned success.
    Assertion rationale: the ack runs first, the fake saw the table and key the
    service passed on, the returned result is the store's, and the scope closed.
    """
    registrar = FakeSlackRegistrar(service_scopes=SvcsServiceScopeOpener(service_registry))
    register(registrar)
    tracked_record_store.store.get.return_value = OperationResult.success(data={"id": "INC-1"})
    ack = MagicMock()

    result = registrar.block_actions[_ACTION_ID](ack=ack, body={"key": {"pk": "INC-1"}})

    ack.assert_called_once_with()
    assert isinstance(result, OperationResult)
    assert result.is_success
    assert result.data == {"id": "INC-1"}
    tracked_record_store.store.get.assert_called_once_with(_TABLE, {"pk": "INC-1"})
    assert tracked_record_store.closed == [tracked_record_store.store]


async def test_slack_listener_closes_its_scope_when_the_lookup_raises(
    service_registry: svcs.Registry, tracked_record_store: _StoreTracking
) -> None:
    """A failure inside the listener's scope closes the scope and reaches the Bolt caller.

    Stub strategy: the fake store's get raises, so the failure happens while the
    scope is open.
    Assertion rationale: pytest.raises shows the error propagates unchanged, and
    the recorded cleanup shows the scope closed on the failure path.
    """
    registrar = FakeSlackRegistrar(service_scopes=SvcsServiceScopeOpener(service_registry))
    register(registrar)
    tracked_record_store.store.get.side_effect = _LookupFailedError("store unavailable")

    with pytest.raises(_LookupFailedError):
        registrar.block_actions[_ACTION_ID](ack=MagicMock(), body={"key": {"pk": "INC-1"}})

    assert tracked_record_store.closed == [tracked_record_store.store]


async def test_job_resolves_the_record_store_through_the_registry_opener(
    service_registry: svcs.Registry, tracked_record_store: _StoreTracking
) -> None:
    """A job opens a scope from the registry, resolves RecordStore, and calls the service once.

    Stub strategy: the recording registry carries the host opener over the
    fixture registry; the job is invoked directly, as the scheduler would.
    Assertion rationale: the fake saw exactly one get with the key the job chose,
    and the scope the job opened has closed when the job returns.
    """
    registry = _RecordingJobRegistry(SvcsServiceScopeOpener(service_registry))
    register_job(registry)
    tracked_record_store.store.get.return_value = OperationResult.success(data={"id": "INC-1"})

    registry.jobs[_JOB_NAME]()

    tracked_record_store.store.get.assert_called_once_with(_TABLE, {"pk": "INC-1"})
    assert tracked_record_store.closed == [tracked_record_store.store]


async def test_job_closes_its_scope_when_the_lookup_raises(
    service_registry: svcs.Registry, tracked_record_store: _StoreTracking
) -> None:
    """A failure inside the job's scope closes the scope and propagates to the scheduler.

    Stub strategy: the fake store's get raises while the job's scope is open.
    Assertion rationale: the exception is not swallowed by the job, and the
    recorded cleanup shows the scope closed on the failure path.
    """
    registry = _RecordingJobRegistry(SvcsServiceScopeOpener(service_registry))
    register_job(registry)
    tracked_record_store.store.get.side_effect = _LookupFailedError("store unavailable")

    with pytest.raises(_LookupFailedError):
        registry.jobs[_JOB_NAME]()

    assert tracked_record_store.closed == [tracked_record_store.store]
