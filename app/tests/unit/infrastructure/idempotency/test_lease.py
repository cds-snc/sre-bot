"""Unit tests for shared lease helpers over IdempotencyStore.

These tests assert reusable lease semantics for singleton execution paths.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

import pytest

from infrastructure import idempotency
from infrastructure.idempotency import IdempotencySettings, InMemoryIdempotencyStore

pytestmark = pytest.mark.unit


def _lease_api() -> tuple[Callable[[object, str], bool], Callable[[object, str], None]]:
    acquire = getattr(idempotency, "acquire_lease", None)
    release = getattr(idempotency, "release_lease", None)

    assert callable(acquire), "infrastructure.idempotency.acquire_lease must be exported"
    assert callable(release), "infrastructure.idempotency.release_lease must be exported"
    return acquire, release


def _store() -> InMemoryIdempotencyStore:
    settings = IdempotencySettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300)
    return InMemoryIdempotencyStore(idempotency_settings=settings)


def test_acquire_lease_returns_true_once_for_same_name() -> None:
    acquire_lease, _ = _lease_api()
    store = _store()

    assert acquire_lease(store, "leases:access-sync:platform:aws") is True
    assert acquire_lease(store, "leases:access-sync:platform:aws") is False


def test_release_lease_allows_name_to_be_claimed_again() -> None:
    acquire_lease, release_lease = _lease_api()
    store = _store()
    name = "leases:access-sync:user:aws:alice@example.com"

    assert acquire_lease(store, name) is True
    release_lease(store, name)
    assert acquire_lease(store, name) is True


def test_acquire_lease_concurrent_calls_yield_exactly_one_winner() -> None:
    acquire_lease, _ = _lease_api()
    store = _store()
    barrier = threading.Barrier(2)
    results: list[bool] = []

    def _worker() -> None:
        barrier.wait()
        results.append(acquire_lease(store, "leases:access-sync:platform:aws"))

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results.count(True) == 1
    assert results.count(False) == 1
