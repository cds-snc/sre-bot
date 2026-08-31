"""Unit tests for shared lease helpers over IdempotencyStore.

These tests assert reusable lease semantics for singleton execution paths.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from unittest.mock import MagicMock

import pytest

from infrastructure import idempotency
from infrastructure.idempotency import (
    IdempotencySettings,
    InMemoryIdempotencyStore,
    acquire_lease,
    get_lease_store,
    run_if_leased,
)

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


class TestGetLeaseStore:
    """Tests for the TTL-parameterized lease store factory."""

    @pytest.mark.unit
    def test_get_lease_store_returns_singleton_per_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_lease_store(ttl) called twice with the same ttl returns the same instance."""
        monkeypatch.setattr(
            "infrastructure.idempotency.factory.get_aws_client",
            MagicMock(return_value=MagicMock(spec=["put_item", "get_item", "delete_item"])),
            raising=False,
        )
        try:
            store1 = get_lease_store(600)
            store2 = get_lease_store(600)

            # Should be the same instance for the same TTL
            assert store1 is store2
        finally:
            get_lease_store.cache_clear()

    @pytest.mark.unit
    def test_get_lease_store_returns_distinct_instance_for_different_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_lease_store(ttl) called with different ttls returns different instances."""
        monkeypatch.setattr(
            "infrastructure.idempotency.factory.get_aws_client",
            MagicMock(return_value=MagicMock(spec=["put_item", "get_item", "delete_item"])),
            raising=False,
        )
        try:
            store1 = get_lease_store(600)
            store2 = get_lease_store(1800)

            # Should be different instances for different TTLs
            assert store1 is not store2
        finally:
            get_lease_store.cache_clear()


class TestRunIfLeased:
    """Tests for the acquire+run+release convenience wrapper."""

    @pytest.mark.unit
    def test_run_if_leased_executes_job_when_acquired(self) -> None:
        """run_if_leased executes the job and releases the lease when acquired."""
        store = _store()
        job = MagicMock()

        run_if_leased(store, "scheduler:test_job", job)

        job.assert_called_once()

    @pytest.mark.unit
    def test_run_if_leased_skips_job_when_lease_held(self) -> None:
        """run_if_leased does not execute the job when the lease is already held."""
        store = _store()
        job = MagicMock()

        # Acquire the lease first
        assert acquire_lease(store, "scheduler:test_job") is True

        # Second call to run_if_leased should not execute the job
        run_if_leased(store, "scheduler:test_job", job)

        job.assert_not_called()

    @pytest.mark.unit
    def test_run_if_leased_releases_lease_even_on_job_exception(self) -> None:
        """run_if_leased releases the lease even when job raises an exception."""
        store = _store()

        def failing_job() -> None:
            raise ValueError("Job failed")

        failing_job.__name__ = "failing_job"

        # First call: job raises, lease should be released
        with pytest.raises(ValueError, match="Job failed"):
            run_if_leased(store, "scheduler:test_job", failing_job)

        # Second call should be able to acquire the lease again
        successful_job = MagicMock()
        run_if_leased(store, "scheduler:test_job", successful_job)

        successful_job.assert_called_once()

    @pytest.mark.unit
    def test_run_if_leased_takes_over_expired_lease(self) -> None:
        """run_if_leased takes over an expired lease and executes the job."""
        # Build a store with a negative TTL so the lease expires immediately
        settings = IdempotencySettings(
            IDEMPOTENCY_TTL_SECONDS=3600,
            IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=0,  # Expires immediately
        )
        expired_store = InMemoryIdempotencyStore(idempotency_settings=settings)

        # First call: acquire and hold the lease (expires immediately after)
        first_job = MagicMock()
        run_if_leased(expired_store, "scheduler:test_job", first_job)
        first_job.assert_called_once()

        # Reset call count and make a second call
        # Since the lease expired, it should be taken over and the job should run
        second_job = MagicMock()
        run_if_leased(expired_store, "scheduler:test_job", second_job)

        second_job.assert_called_once()
