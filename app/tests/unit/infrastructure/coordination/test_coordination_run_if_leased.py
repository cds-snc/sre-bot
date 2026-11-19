"""Unit tests for run_if_leased, the host's lease enforcement around a job.

Lease correctness comes from the LeaseStore facade over the real in-memory
primitive, so these tests cover only acquire-run-release orchestration: skip when
held, release on failure, takeover after expiry, and no release of a lease that a
second holder took over mid-run. The minimum-hold cases move time with freezegun:
a run shorter than its hold keeps the lease until start plus the hold.
"""

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from contracts.coordination import ClaimOutcome, ClaimResult, LeaseStore, ReadFailurePolicy
from infrastructure.coordination import InMemoryConditionalWriteStore, run_if_leased

pytestmark = pytest.mark.unit

NAME = "scheduler:test_job"
FROZEN_START = "2026-11-18 12:00:00"
HOLD = timedelta(seconds=60)


def _lease_store(in_progress_ttl_seconds: int = 300) -> LeaseStore:
    return LeaseStore(
        InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=in_progress_ttl_seconds),
        read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
    )


def test_run_if_leased_executes_job_when_acquired() -> None:
    job = MagicMock()

    run_if_leased(_lease_store(), NAME, job)

    job.assert_called_once()


def test_run_if_leased_skips_job_when_lease_held() -> None:
    lease_store = _lease_store()
    assert lease_store.acquire(NAME) is not None
    job = MagicMock()

    run_if_leased(lease_store, NAME, job)

    job.assert_not_called()


def test_run_if_leased_skips_job_and_release_when_claim_is_indeterminate() -> None:
    """A fail-closed INDETERMINATE claim runs nothing and releases nothing."""
    store = MagicMock()
    store.claim.return_value = ClaimOutcome(result=ClaimResult.INDETERMINATE)
    job = MagicMock()

    run_if_leased(LeaseStore(store, read_failure_policy=ReadFailurePolicy.FAIL_CLOSED), NAME, job)

    job.assert_not_called()
    store.release.assert_not_called()


def test_run_if_leased_releases_lease_even_on_job_exception() -> None:
    lease_store = _lease_store()

    def failing_job() -> None:
        raise ValueError("Job failed")

    with pytest.raises(ValueError, match="Job failed"):
        run_if_leased(lease_store, NAME, failing_job)

    successful_job = MagicMock()
    run_if_leased(lease_store, NAME, successful_job)
    successful_job.assert_called_once()


def test_run_if_leased_takes_over_expired_lease() -> None:
    lease_store = _lease_store(in_progress_ttl_seconds=0)
    first_job = MagicMock()
    second_job = MagicMock()

    run_if_leased(lease_store, NAME, first_job)
    run_if_leased(lease_store, NAME, second_job)

    first_job.assert_called_once()
    second_job.assert_called_once()


def test_run_if_leased_does_not_release_a_lease_taken_over_mid_run() -> None:
    """A job that outlives its TTL must not free the lease a second holder took over.

    The second holder's own release succeeding afterwards proves the record survived.
    """
    lease_store = _lease_store(in_progress_ttl_seconds=-1)
    takeover_tokens: list[str | None] = []

    def job_overtaken_mid_run() -> None:
        takeover_tokens.append(lease_store.acquire(NAME))

    run_if_leased(lease_store, NAME, job_overtaken_mid_run)

    [takeover_token] = takeover_tokens
    assert takeover_token is not None
    assert lease_store.release(NAME, takeover_token) is True


class TestMinimumHold:
    def test_short_run_keeps_the_lease_until_start_plus_the_hold(self) -> None:
        lease_store = _lease_store()
        second_job = MagicMock()
        with freeze_time(FROZEN_START) as frozen:
            run_if_leased(lease_store, NAME, MagicMock(), min_hold=HOLD)
            frozen.tick(60)
            run_if_leased(lease_store, NAME, second_job, min_hold=HOLD)
            second_job.assert_not_called()

            frozen.tick(1)
            run_if_leased(lease_store, NAME, second_job, min_hold=HOLD)

        second_job.assert_called_once()

    def test_failed_short_run_holds_and_re_raises(self) -> None:
        lease_store = _lease_store()

        def failing_job() -> None:
            raise ValueError("Job failed")

        with freeze_time(FROZEN_START):
            with pytest.raises(ValueError, match="Job failed"):
                run_if_leased(lease_store, NAME, failing_job, min_hold=HOLD)

            assert lease_store.acquire(NAME) is None

    def test_run_longer_than_the_hold_releases_at_end(self) -> None:
        lease_store = _lease_store()
        with freeze_time(FROZEN_START) as frozen:
            run_if_leased(lease_store, NAME, lambda: frozen.tick(61), min_hold=HOLD)

            assert lease_store.acquire(NAME) is not None

    def test_held_release_does_not_touch_a_lease_taken_over_mid_run(self) -> None:
        lease_store = _lease_store(in_progress_ttl_seconds=-1)
        takeover_tokens: list[str | None] = []

        with freeze_time(FROZEN_START):
            run_if_leased(lease_store, NAME, lambda: takeover_tokens.append(lease_store.acquire(NAME)), min_hold=HOLD)

        [takeover_token] = takeover_tokens
        assert takeover_token is not None
        assert lease_store.release(NAME, takeover_token) is True


class _FailOpenClaimStore:
    """Delegates to a real store but answers claim with NEW and a token no record holds.

    That is what a fail-open lease acquire (TASK-100) hands the caller: the job runs
    while the store holds nothing under that token, so its release must free and
    hold nothing.
    """

    def __init__(self, store: InMemoryConditionalWriteStore) -> None:
        self._store = store

    def claim(self, key: str) -> ClaimOutcome:
        return ClaimOutcome(result=ClaimResult.NEW, claim_token="f" * 32)

    def complete(self, key: str, outcome: dict[str, Any], claim_token: str) -> bool:
        return self._store.complete(key, outcome, claim_token)

    def release(self, key: str, claim_token: str) -> bool:
        return self._store.release(key, claim_token)

    def expire_at(self, key: str, claim_token: str, at: int) -> bool:
        return self._store.expire_at(key, claim_token, at)


class TestFailOpenHeldRelease:
    def test_held_release_of_a_fail_open_lease_leaves_another_holder_untouched(self) -> None:
        """The other replica's lease keeps its own expiry: freeable by its holder, and
        not extended by the fail-open caller's hold."""
        store = InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300)
        holder = LeaseStore(store, read_failure_policy=ReadFailurePolicy.FAIL_CLOSED)
        fail_open = LeaseStore(_FailOpenClaimStore(store), read_failure_policy=ReadFailurePolicy.FAIL_CLOSED)
        job = MagicMock()

        with freeze_time(FROZEN_START) as frozen:
            token = holder.acquire(NAME)
            assert token is not None
            run_if_leased(fail_open, NAME, job, min_hold=timedelta(seconds=1000))
            frozen.tick(301)
            takeover = holder.acquire(NAME)

        job.assert_called_once()
        assert takeover is not None

    def test_held_release_of_a_fail_open_lease_creates_nothing(self) -> None:
        store = InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300)
        fail_open = LeaseStore(_FailOpenClaimStore(store), read_failure_policy=ReadFailurePolicy.FAIL_CLOSED)

        with freeze_time(FROZEN_START):
            run_if_leased(fail_open, NAME, MagicMock(), min_hold=HOLD)
            acquired = LeaseStore(store, read_failure_policy=ReadFailurePolicy.FAIL_CLOSED).acquire(NAME)

        assert acquired is not None
