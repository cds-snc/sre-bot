"""Unit tests for shared lease helpers over ConditionalWriteStore.

These tests assert reusable lease semantics for singleton execution paths.
"""

import threading
from collections.abc import Callable
from unittest.mock import MagicMock

import pytest

from infrastructure import coordination
from infrastructure.coordination import (
    ConditionalWriteSettings,
    InMemoryConditionalWriteStore,
    acquire_lease,
    get_lease_store,
    run_if_leased,
)

pytestmark = pytest.mark.unit


def _lease_api() -> tuple[Callable[[object, str], str | None], Callable[[object, str, str], bool]]:
    acquire = getattr(coordination, "acquire_lease", None)
    release = getattr(coordination, "release_lease", None)

    assert callable(acquire), "infrastructure.coordination.acquire_lease must be exported"
    assert callable(release), "infrastructure.coordination.release_lease must be exported"
    return acquire, release


def _store() -> InMemoryConditionalWriteStore:
    settings = ConditionalWriteSettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300)
    return InMemoryConditionalWriteStore(settings=settings)


def test_acquire_lease_returns_a_token_once_for_same_name() -> None:
    acquire_lease, _ = _lease_api()
    store = _store()

    assert acquire_lease(store, "leases:access-sync:platform:aws")
    assert acquire_lease(store, "leases:access-sync:platform:aws") is None


def test_release_lease_allows_name_to_be_claimed_again() -> None:
    acquire_lease, release_lease = _lease_api()
    store = _store()
    name = "leases:access-sync:user:aws:alice@example.com"

    claim_token = acquire_lease(store, name)
    assert claim_token is not None
    assert release_lease(store, name, claim_token) is True
    assert acquire_lease(store, name) is not None


def test_release_lease_with_a_foreign_token_keeps_the_lease() -> None:
    acquire_lease, release_lease = _lease_api()
    store = _store()
    name = "leases:access-sync:platform:aws"
    acquire_lease(store, name)

    assert release_lease(store, name, "0" * 32) is False
    assert acquire_lease(store, name) is None


def test_acquire_lease_concurrent_calls_yield_exactly_one_winner() -> None:
    acquire_lease, _ = _lease_api()
    store = _store()
    barrier = threading.Barrier(2)
    results: list[str | None] = []

    def _worker() -> None:
        barrier.wait()
        results.append(acquire_lease(store, "leases:access-sync:platform:aws"))

    t1 = threading.Thread(target=_worker)
    t2 = threading.Thread(target=_worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results.count(None) == 1
    assert len([token for token in results if token]) == 1


class TestGetLeaseStore:
    """Tests for the TTL-parameterized lease store factory."""

    @pytest.mark.unit
    def test_get_lease_store_returns_singleton_per_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """get_lease_store(ttl) called twice with the same ttl returns the same instance."""
        monkeypatch.setattr(
            "infrastructure.coordination.factory.get_aws_client",
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
            "infrastructure.coordination.factory.get_aws_client",
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
        assert acquire_lease(store, "scheduler:test_job") is not None

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
        settings = ConditionalWriteSettings(
            IDEMPOTENCY_TTL_SECONDS=3600,
            IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=0,  # Expires immediately
        )
        expired_store = InMemoryConditionalWriteStore(settings=settings)

        # First call: acquire and hold the lease (expires immediately after)
        first_job = MagicMock()
        run_if_leased(expired_store, "scheduler:test_job", first_job)
        first_job.assert_called_once()

        # Reset call count and make a second call
        # Since the lease expired, it should be taken over and the job should run
        second_job = MagicMock()
        run_if_leased(expired_store, "scheduler:test_job", second_job)

        second_job.assert_called_once()

    @pytest.mark.unit
    def test_run_if_leased_does_not_release_a_lease_taken_over_mid_run(self) -> None:
        """A job that outlives its TTL must not free the lease a second holder took over.

        The second holder's own release succeeding afterwards proves the record survived.
        """
        settings = ConditionalWriteSettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=-1)
        expired_store = InMemoryConditionalWriteStore(settings=settings)
        name = "scheduler:test_job"
        takeover_tokens: list[str | None] = []

        def job_overtaken_mid_run() -> None:
            takeover_tokens.append(acquire_lease(expired_store, name))

        run_if_leased(expired_store, name, job_overtaken_mid_run)

        [takeover_token] = takeover_tokens
        assert takeover_token is not None
        assert expired_store.release(name, takeover_token) is True
