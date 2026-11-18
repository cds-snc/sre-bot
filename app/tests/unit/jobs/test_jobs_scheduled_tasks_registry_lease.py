"""Unit tests for the optional lease on feature jobs registered through the scheduler registry.

The schedule library is a MagicMock, so registration captures the callable the
registry schedules without running a scheduler; that callable is then invoked
directly. get_lease_store is patched to return a real LeaseStore over the
in-memory conditional-write store, so lease acquisition and a held lease behave
as in production without DynamoDB. The tests assert that no lease is taken
without lease_ttl, that a TTL leases the job under scheduler:<job_name> with the
TTL in whole seconds, that a lease another replica holds skips the run, that an expired lease
lets the job run again, that a failing job is still caught by safe_run, and that a
non-positive TTL is rejected at registration. The minimum-hold cases capture the
hold the registry hands run_if_leased, min(TTL, interval - margin) with the margin
from the scheduler settings, and drive the held lease with freezegun.
"""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

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


def _register(
    cadence: str, job: Callable[[], None], lease_ttl: timedelta | None, every: timedelta = timedelta(minutes=5)
) -> None:
    registry = _ScheduleBackgroundJobRegistry(service_scopes=MagicMock(name="scope_opener"))
    if cadence == "daily":
        registry.register_daily(job_name="upgrade", schedule="03:30", job=job, lease_ttl=lease_ttl)
    else:
        registry.register_interval(job_name="upgrade", every=every, job=job, lease_ttl=lease_ttl)


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
    with patch("jobs.scheduled_tasks.run_if_leased", side_effect=lambda store, name, body, **_: body()) as run_if_leased:
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


@pytest.mark.parametrize("cadence", ["daily", "interval"])
def test_a_leased_job_runs_again_once_its_hold_has_passed(
    schedule_lib: MagicMock, get_lease_store: MagicMock, cadence: str
) -> None:
    """After a short run the lease is held for its hold (900 s daily, 295 s on a 5 min interval), then the next tick runs."""
    job = MagicMock(__name__="job", __module__="tests")
    with freeze_time("2026-11-18 12:00:00") as frozen:
        _register(cadence, job, timedelta(minutes=15))
        run = _scheduled(schedule_lib, cadence)
        run()
        frozen.tick(901)
        run()

    assert job.call_count == 2


@pytest.mark.parametrize(
    ("cadence", "every", "lease_ttl", "hold"),
    [
        pytest.param("interval", timedelta(minutes=5), timedelta(minutes=30), timedelta(seconds=295), id="interval-under-ttl"),
        pytest.param("interval", timedelta(minutes=30), timedelta(minutes=15), timedelta(minutes=15), id="upgrade-job-ttl-caps"),
        pytest.param("interval", timedelta(minutes=5), timedelta(seconds=60), timedelta(seconds=60), id="short-ttl-caps"),
        pytest.param("daily", timedelta(minutes=5), timedelta(minutes=30), timedelta(minutes=30), id="daily-holds-its-ttl"),
    ],
)
def test_the_hold_is_the_ttl_or_the_interval_less_the_margin_whichever_is_shorter(
    schedule_lib: MagicMock, get_lease_store: MagicMock, cadence: str, every: timedelta, lease_ttl: timedelta, hold: timedelta
) -> None:
    with patch("jobs.scheduled_tasks.run_if_leased") as run_if_leased:
        _register(cadence, MagicMock(__name__="job", __module__="tests"), lease_ttl, every)
        _scheduled(schedule_lib, cadence)()

    assert run_if_leased.call_args.kwargs["min_hold"] == hold


@pytest.mark.parametrize(("margin", "hold"), [(0, timedelta(minutes=5)), (60, timedelta(minutes=4))])
def test_the_margin_comes_from_the_scheduler_settings(
    schedule_lib: MagicMock, get_lease_store: MagicMock, margin: int, hold: timedelta
) -> None:
    settings = MagicMock(lease_hold_margin_seconds=margin)
    with (
        patch("jobs.scheduled_tasks.get_scheduler_settings", return_value=settings),
        patch("jobs.scheduled_tasks.run_if_leased") as run_if_leased,
    ):
        _register("interval", MagicMock(__name__="job", __module__="tests"), timedelta(minutes=30))
        _scheduled(schedule_lib, "interval")()

    assert run_if_leased.call_args.kwargs["min_hold"] == hold


@pytest.mark.parametrize("every", [timedelta(seconds=5), timedelta(seconds=2)])
def test_a_leased_interval_at_or_under_the_margin_is_rejected_at_registration(
    schedule_lib: MagicMock, get_lease_store: MagicMock, every: timedelta
) -> None:
    """With no room for a hold the replicas would run every tick twice; fail startup instead."""
    with pytest.raises(ValueError, match="upgrade"):
        _register("interval", MagicMock(__name__="job", __module__="tests"), timedelta(minutes=30), every)

    schedule_lib.every.assert_not_called()


def test_a_tier1_interval_under_the_margin_registers(schedule_lib: MagicMock, get_lease_store: MagicMock) -> None:
    job = MagicMock(__name__="job", __module__="tests")
    _register("interval", job, None, timedelta(seconds=2))

    _scheduled(schedule_lib, "interval")()

    job.assert_called_once()
    get_lease_store.assert_not_called()


def test_a_short_leased_run_holds_the_lease_until_just_before_the_next_interval(
    schedule_lib: MagicMock, get_lease_store: MagicMock
) -> None:
    """Interval 5 min, TTL 30 min: the lease is held 295 s after the start, free after."""
    job = MagicMock(__name__="job", __module__="tests")
    leases = get_lease_store.return_value
    with freeze_time("2026-11-18 12:00:00") as frozen:
        _register("interval", job, timedelta(minutes=30))
        _scheduled(schedule_lib, "interval")()
        frozen.tick(295)
        during = leases.acquire("scheduler:upgrade")
        frozen.tick(1)
        after = leases.acquire("scheduler:upgrade")

    job.assert_called_once()
    assert during is None
    assert after is not None


@pytest.mark.parametrize(("cadence", "hold_seconds"), [("daily", 1800), ("interval", 295)])
def test_the_scheduled_event_names_the_hold(
    schedule_lib: MagicMock, get_lease_store: MagicMock, cadence: str, hold_seconds: int
) -> None:
    with patch("jobs.scheduled_tasks.logger") as logger:
        _register(cadence, MagicMock(__name__="job", __module__="tests"), timedelta(minutes=30))

    assert logger.debug.call_args.kwargs["lease_min_hold_seconds"] == hold_seconds


def test_a_tier1_scheduled_event_has_no_hold(schedule_lib: MagicMock, get_lease_store: MagicMock) -> None:
    with patch("jobs.scheduled_tasks.logger") as logger:
        _register("interval", MagicMock(__name__="job", __module__="tests"), None)

    assert logger.debug.call_args.kwargs["lease_min_hold_seconds"] is None
