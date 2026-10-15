"""Unit tests for SvcsServiceScopeOpener, the server's ServiceScopeOpener.

The opener runs over the service_registry fixture, so each create_scope() builds a real
svcs.Container over the fixture's registry. A scope's close is observed through
a generator factory: svcs runs the cleanup of a generator-registered service when
its container closes, so a recorded cleanup proves the scope was closed. The
fixture's ConditionalWriteStore is re-registered as such a factory, which yields
a fresh MagicMock per container and records each one's cleanup.
"""

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest
import svcs

from contracts.coordination import ConditionalWriteStore
from contracts.records import RecordStore
from infrastructure.records.in_memory import InMemoryRecordStore
from server.services import SvcsServiceScopeOpener

pytestmark = pytest.mark.unit


class _Unregistered:
    """A contract the host never registers."""


class _BodyFailedError(Exception):
    """Raised inside a scope to show the exception still reaches the caller after the scope closes."""


@dataclass
class _ScopeRecord:
    """Instances built by the tracked factory, in creation order, and the ones whose cleanup ran."""

    created: list[ConditionalWriteStore] = field(default_factory=list)
    closed: list[ConditionalWriteStore] = field(default_factory=list)


@pytest.fixture
async def scope_record(service_registry: svcs.Registry) -> _ScopeRecord:
    """Re-register ConditionalWriteStore as a generator factory that records its own cleanup."""
    record = _ScopeRecord()

    def tracked_store() -> Iterator[ConditionalWriteStore]:
        store = MagicMock(spec=ConditionalWriteStore)
        record.created.append(store)
        yield store
        record.closed.append(store)

    service_registry.register_factory(ConditionalWriteStore, tracked_store)
    return record


async def test_open_resolves_the_registered_record_store(service_registry: svcs.Registry) -> None:
    """A scope yields a resolver that returns the RecordStore the registry holds.

    Stub strategy: the fixture's in-memory RecordStore is the registered entry.
    Assertion rationale: the concrete type proves the resolver reads the host
    registry rather than building its own.
    """
    opener = SvcsServiceScopeOpener(service_registry)

    with opener.create_scope() as resolver:
        store = resolver.get(RecordStore)

    assert isinstance(store, InMemoryRecordStore)


async def test_open_fails_with_the_registry_not_found_error_for_an_unregistered_contract(
    service_registry: svcs.Registry,
) -> None:
    """Resolving a contract the registry lacks raises svcs' ServiceNotFoundError.

    Stub strategy: the fixture registry is used unchanged; _Unregistered is never
    registered in it.
    Assertion rationale: the error type is the registry's own, so an entry point
    can distinguish a missing registration from a failing factory.
    """
    opener = SvcsServiceScopeOpener(service_registry)

    with pytest.raises(svcs.exceptions.ServiceNotFoundError), opener.create_scope() as resolver:
        resolver.get(_Unregistered)


async def test_scope_closes_its_container_on_normal_exit(service_registry: svcs.Registry, scope_record: _ScopeRecord) -> None:
    """Leaving the scope normally runs the cleanup of the service it built.

    Stub strategy: the tracked factory yields a MagicMock and records its cleanup.
    Assertion rationale: the cleanup list matches the created instances, so the
    container closed and the service it built was torn down.
    """
    opener = SvcsServiceScopeOpener(service_registry)

    with opener.create_scope() as resolver:
        resolver.get(ConditionalWriteStore)

    assert len(scope_record.created) == 1
    assert scope_record.closed == scope_record.created


async def test_scope_closes_its_container_when_the_body_raises(
    service_registry: svcs.Registry, scope_record: _ScopeRecord
) -> None:
    """An exception raised inside the scope still closes the container and propagates.

    Stub strategy: the body resolves the tracked service and then raises a
    test-local exception.
    Assertion rationale: the cleanup runs on the failure path, and pytest.raises
    shows the original exception was not swallowed or replaced.
    """
    opener = SvcsServiceScopeOpener(service_registry)

    with pytest.raises(_BodyFailedError), opener.create_scope() as resolver:
        resolver.get(ConditionalWriteStore)
        raise _BodyFailedError

    assert len(scope_record.created) == 1
    assert scope_record.closed == scope_record.created


async def test_each_open_builds_an_independent_container_closed_once(
    service_registry: svcs.Registry, scope_record: _ScopeRecord
) -> None:
    """Two sequential opens build two services, and each is cleaned up exactly once.

    Stub strategy: the tracked factory builds a new MagicMock per container, so a
    shared container would show up as one instance.
    Assertion rationale: two distinct instances and two cleanups prove each open
    has its own container, with no scope reused across invocations.
    """
    opener = SvcsServiceScopeOpener(service_registry)

    with opener.create_scope() as first:
        first.get(ConditionalWriteStore)
    with opener.create_scope() as second:
        second.get(ConditionalWriteStore)

    assert len(scope_record.created) == 2
    assert scope_record.created[0] is not scope_record.created[1]
    assert scope_record.closed == scope_record.created


async def test_concurrent_opens_from_worker_threads_each_close_their_own_container(
    service_registry: svcs.Registry, scope_record: _ScopeRecord
) -> None:
    """Opens running on worker threads each build and close their own container.

    Stub strategy: eight invocations run through asyncio.to_thread, the way
    synchronous Bolt listeners run on worker threads. The tracked factory is the
    same as above.
    Assertion rationale: eight distinct instances, each cleaned up once, show the
    opener keeps no shared container between threads.
    """
    opener = SvcsServiceScopeOpener(service_registry)

    def invoke() -> None:
        with opener.create_scope() as resolver:
            resolver.get(ConditionalWriteStore)

    await asyncio.gather(*(asyncio.to_thread(invoke) for _ in range(8)))

    assert len({id(store) for store in scope_record.created}) == 8
    assert sorted(map(id, scope_record.closed)) == sorted(map(id, scope_record.created))
