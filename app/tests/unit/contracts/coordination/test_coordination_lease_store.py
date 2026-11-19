"""Unit tests for the LeaseStore facade over ConditionalWriteStore.

Lifecycle cases run on the real in-memory primitive, so takeover and ownership
follow the store's actual rules. The INDETERMINATE case uses a scripted store,
because no real store reports it without a failing read, and checks that a
fail-closed lease is simply not acquired. The held-release cases move time with
freezegun; the store holds a lease through its expiry second inclusive.
"""

import threading
import time

import pytest
from freezegun import freeze_time

from contracts.coordination import ClaimOutcome, ClaimResult, ConditionalWriteStore, LeaseStore, ReadFailurePolicy
from infrastructure.coordination import InMemoryConditionalWriteStore

from .conftest import ScriptedConditionalWriteStore

pytestmark = pytest.mark.unit

NAME = "leases:access-sync:platform:aws"
FROZEN_START = "2026-11-18 12:00:00"


def _lease_store(store: ConditionalWriteStore) -> LeaseStore:
    return LeaseStore(store, read_failure_policy=ReadFailurePolicy.FAIL_CLOSED)


class TestLeaseStoreConstruction:
    def test_read_failure_policy_is_required(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        with pytest.raises(TypeError):
            LeaseStore(in_memory_store)  # type: ignore[call-arg]

    def test_read_failure_policy_is_keyword_only(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        with pytest.raises(TypeError):
            LeaseStore(in_memory_store, ReadFailurePolicy.FAIL_CLOSED)  # type: ignore[misc]


class TestLeaseStoreLifecycle:
    def test_acquire_returns_a_token_once_for_the_same_name(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        leases = _lease_store(in_memory_store)

        assert leases.acquire(NAME)
        assert leases.acquire(NAME) is None

    def test_release_by_holder_makes_the_name_acquirable_again(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        leases = _lease_store(in_memory_store)
        claim_token = leases.acquire(NAME)
        assert claim_token is not None

        assert leases.release(NAME, claim_token) is True
        assert leases.acquire(NAME) is not None

    def test_release_with_a_foreign_token_keeps_the_lease(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        leases = _lease_store(in_memory_store)
        leases.acquire(NAME)

        assert leases.release(NAME, "0" * 32) is False
        assert leases.acquire(NAME) is None

    def test_expired_lease_is_taken_over(self, expired_store: InMemoryConditionalWriteStore) -> None:
        leases = _lease_store(expired_store)
        first = leases.acquire(NAME)

        second = leases.acquire(NAME)

        assert first is not None
        assert second is not None
        assert second != first

    def test_completed_record_is_not_acquirable(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        claim_token = in_memory_store.claim(NAME).claim_token
        assert claim_token is not None
        in_memory_store.complete(NAME, {"status": "done"}, claim_token)

        assert _lease_store(in_memory_store).acquire(NAME) is None

    def test_concurrent_acquire_has_exactly_one_winner(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        leases = _lease_store(in_memory_store)
        barrier = threading.Barrier(2)
        results: list[str | None] = []

        def _worker() -> None:
            barrier.wait()
            results.append(leases.acquire(NAME))

        threads = [threading.Thread(target=_worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert results.count(None) == 1


class TestLeaseStoreReadFailure:
    def test_fail_closed_indeterminate_claim_is_not_acquired(self) -> None:
        """A failed contended re-read leaves the lease unacquired and nothing to release."""
        store = ScriptedConditionalWriteStore(ClaimOutcome(result=ClaimResult.INDETERMINATE))

        assert _lease_store(store).acquire(NAME) is None
        assert store.calls == [("claim", NAME)]

    def test_release_reports_lost_ownership_as_false(self) -> None:
        store = ScriptedConditionalWriteStore(ownership=False)

        assert _lease_store(store).release(NAME, "a" * 32) is False
        assert store.calls == [("release", NAME, "a" * 32)]


class TestLeaseStoreHeldRelease:
    """release(not_before=) keeps the lease until that instant; None or a past instant deletes as before."""

    def test_future_not_before_keeps_the_lease_until_then(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        leases = _lease_store(in_memory_store)
        with freeze_time(FROZEN_START) as frozen:
            token = leases.acquire(NAME)
            assert token is not None

            released = leases.release(NAME, token, not_before=time.time() + 60)
            frozen.tick(60)
            during = leases.acquire(NAME)
            frozen.tick(1)
            after = leases.acquire(NAME)

        assert released is True
        assert during is None
        assert after is not None

    def test_fractional_not_before_is_floored_and_still_held_through_it(
        self, in_memory_store: InMemoryConditionalWriteStore
    ) -> None:
        """Flooring keeps a hold equal to the TTL within the acquire-time expiry; the
        inclusive expiry second still covers the instant itself."""
        leases = _lease_store(in_memory_store)
        with freeze_time("2026-11-18 12:00:00.400") as frozen:
            token = leases.acquire(NAME)
            assert token is not None
            not_before = time.time() + 300

            leases.release(NAME, token, not_before=not_before)
            frozen.tick(300)
            at_not_before = leases.acquire(NAME)
            frozen.tick(0.6)
            past_the_ttl_expiry = leases.acquire(NAME)

        assert at_not_before is None
        assert past_the_ttl_expiry is not None

    def test_none_not_before_deletes_as_before(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        leases = _lease_store(in_memory_store)
        token = leases.acquire(NAME)
        assert token is not None

        assert leases.release(NAME, token, not_before=None) is True
        assert leases.acquire(NAME) is not None

    def test_past_not_before_deletes(self, in_memory_store: InMemoryConditionalWriteStore) -> None:
        leases = _lease_store(in_memory_store)
        with freeze_time(FROZEN_START):
            token = leases.acquire(NAME)
            assert token is not None

            assert leases.release(NAME, token, not_before=time.time() - 1) is True
            assert leases.acquire(NAME) is not None

    def test_stale_holder_held_release_returns_false_and_keeps_the_new_holder_lease(
        self, expired_store: InMemoryConditionalWriteStore
    ) -> None:
        leases = _lease_store(expired_store)
        stale = leases.acquire(NAME)
        current = leases.acquire(NAME)
        assert stale is not None
        assert current is not None

        assert leases.release(NAME, stale, not_before=time.time() + 600) is False
        assert leases.release(NAME, current) is True

    def test_future_not_before_calls_expire_at_with_the_floored_second(self) -> None:
        store = ScriptedConditionalWriteStore()
        with freeze_time(FROZEN_START):
            not_before = time.time() + 30.9

            _lease_store(store).release(NAME, "a" * 32, not_before=not_before)

        assert store.calls == [("expire_at", NAME, "a" * 32, str(int(not_before)))]

    def test_past_or_absent_not_before_calls_release(self) -> None:
        store = ScriptedConditionalWriteStore()
        leases = _lease_store(store)
        with freeze_time(FROZEN_START):
            leases.release(NAME, "a" * 32, not_before=time.time())
            leases.release(NAME, "b" * 32)

        assert store.calls == [("release", NAME, "a" * 32), ("release", NAME, "b" * 32)]

    def test_not_before_is_keyword_only(self) -> None:
        store = ScriptedConditionalWriteStore()

        with pytest.raises(TypeError):
            _lease_store(store).release(NAME, "a" * 32, 1.0)  # type: ignore[misc]
