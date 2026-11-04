"""Unit tests for the optional lease on feature jobs registered through the scheduler registry.

The schedule library is a MagicMock, so registration captures the callable the
registry schedules without running a scheduler; that callable is then invoked
directly. get_lease_store is patched to return a real LeaseStore over the
in-memory conditional-write store, so lease acquisition and a held lease behave
as in production without DynamoDB. The tests assert that no lease is taken
without lease_ttl, that a TTL leases the job under scheduler:<job_name> with the
TTL in whole seconds, that a lease another replica holds skips the run, that a failing job is
still caught by safe_run, and that a non-positive TTL is rejected at registration.
"""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.coordination import LeaseStore, ReadFailurePolicy
from infrastructure.coordination import InMemoryConditionalWriteStore
from jobs.scheduled_tasks import _ScheduleBackgroundJobRegistry

pytestmark = pytest.mark.unit


def _lease_store() -> LeaseStore:
    return LeaseStore(
        InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=300),
        read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
    )


@pytest.fixture
def schedule_lib() -> Iterator[MagicMock]:
    with patch("jobs.scheduled_tasks.schedule_lib") as lib:
        yield lib


@pytest.fixture
def get_lease_store() -> Iterator[MagicMock]:
    with patch("jobs.scheduled_tasks.get_lease_store", return_value=_lease_store()) as factory:
        yield factory


def _register(cadence: str, job: Callable[[], None], lease_ttl: timedelta | None) -> None:
    registry = _ScheduleBackgroundJobRegistry(service_scopes=MagicMock(name="scope_opener"))
    if cadence == "daily":
        registry.register_daily(job_name="upgrade", schedule="03:30", job=job, lease_ttl=lease_ttl)
    else:
        registry.register_interval(job_name="upgrade", every=timedelta(minutes=5), job=job, lease_ttl=lease_ttl)


def _scheduled(schedule_lib: MagicMock, cadence: str) -> Callable[[], Any]:
    do = (
        schedule_lib.every.return_value.day.at.return_value.do
        if cadence == "daily"
        else schedule_lib.every.return_value.seconds.do
    )
    do.assert_called_once()
    return do.call_args.args[0]


@pytest.mark.parametrize("cadence", ["daily", "interval"])
def test_without_a_lease_ttl_the_job_runs_on_every_call_and_no_lease_store_is_built(
    schedule_lib: MagicMock, get_lease_store: MagicMock, cadence: str
) -> None:
    job = MagicMock(__name__="job", __module__="tests")
    _register(cadence, job, None)

    run = _scheduled(schedule_lib, cadence)
    run()
    run()

    assert job.call_count == 2
    get_lease_store.assert_not_called()


@pytest.mark.parametrize("cadence", ["daily", "interval"])
def test_a_lease_ttl_leases_the_job_under_its_scheduler_name(
    schedule_lib: MagicMock, get_lease_store: MagicMock, cadence: str
) -> None:
    job = MagicMock(__name__="job", __module__="tests")
    with patch("jobs.scheduled_tasks.run_if_leased", side_effect=lambda store, name, body: body()) as run_if_leased:
        _register(cadence, job, timedelta(minutes=15))
        _scheduled(schedule_lib, cadence)()

    get_lease_store.assert_called_once_with(900)
    assert run_if_leased.call_args.args[1] == "scheduler:upgrade"
    job.assert_called_once()


@pytest.mark.parametrize("cadence", ["daily", "interval"])
def test_a_lease_held_by_another_replica_skips_the_run(schedule_lib: MagicMock, get_lease_store: MagicMock, cadence: str) -> None:
    job = MagicMock(__name__="job", __module__="tests")
    _register(cadence, job, timedelta(minutes=15))
    other_replica = get_lease_store.return_value.acquire("scheduler:upgrade")
    assert other_replica is not None

    _scheduled(schedule_lib, cadence)()

    job.assert_not_called()


def test_a_failing_leased_job_is_still_caught_by_safe_run(schedule_lib: MagicMock, get_lease_store: MagicMock) -> None:
    job = MagicMock(side_effect=RuntimeError("boom"), __name__="job", __module__="tests")
    _register("interval", job, timedelta(seconds=1))

    _scheduled(schedule_lib, "interval")()

    job.assert_called_once()


@pytest.mark.parametrize("cadence", ["daily", "interval"])
@pytest.mark.parametrize("ttl", [timedelta(0), timedelta(seconds=-5), timedelta(milliseconds=500)])
def test_a_ttl_under_one_second_is_rejected_at_registration(
    schedule_lib: MagicMock, get_lease_store: MagicMock, cadence: str, ttl: timedelta
) -> None:
    with pytest.raises(ValueError, match="lease_ttl"):
        _register(cadence, MagicMock(__name__="job", __module__="tests"), ttl)

    schedule_lib.every.assert_not_called()
