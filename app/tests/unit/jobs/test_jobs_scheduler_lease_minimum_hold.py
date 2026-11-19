"""Two replicas share one lease store; a short Tier-2 job runs once per tick, not once per replica.

Each replica is its own _ScheduleBackgroundJobRegistry registering the same job;
the schedule library is a MagicMock, so the callable each replica would fire is
captured and fired by hand on that replica's clock. Both replicas' leases come
from one LeaseStore over the real in-memory conditional-write store, standing in
for the shared DynamoDB table. freezegun drives time: the job takes 0.1 s, and
the second replica ticks a moment after the first, as two containers whose clocks
started at different times do. The control drops the hold from run_if_leased to
show the double run the hold closes (seen in production on 2026-11-17: two
reports 0.7 s apart).
"""

from collections.abc import Callable, Iterator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from contracts.coordination import LeaseStore, ReadFailurePolicy
from infrastructure.coordination import InMemoryConditionalWriteStore, run_if_leased
from jobs.scheduled_tasks import _ScheduleBackgroundJobRegistry

pytestmark = pytest.mark.unit

FROZEN_START = "2026-11-18 12:00:00"
TICKS = 3


@pytest.fixture
def schedule_lib() -> Iterator[MagicMock]:
    with patch("jobs.scheduled_tasks.schedule_lib") as lib:
        yield lib


def _shared_lease_store(ttl_seconds: int) -> LeaseStore:
    return LeaseStore(
        InMemoryConditionalWriteStore(record_ttl_seconds=3600, in_progress_ttl_seconds=ttl_seconds),
        read_failure_policy=ReadFailurePolicy.FAIL_CLOSED,
    )


def _runs_per_tick(schedule_lib: MagicMock, *, every: timedelta, lease_ttl: timedelta, replica_gap_seconds: float) -> list[int]:
    """Register the job on two replicas, fire both on each tick, and count the job's runs per tick."""
    runs: list[str] = []
    with freeze_time(FROZEN_START) as frozen:

        def job() -> None:
            runs.append("ran")
            frozen.tick(0.1)

        lease_store = _shared_lease_store(int(lease_ttl.total_seconds()))
        with patch("jobs.scheduled_tasks.get_lease_store", return_value=lease_store):
            for _ in range(2):
                _ScheduleBackgroundJobRegistry(service_scopes=MagicMock()).register_interval(
                    job_name="short_job", every=every, job=job, lease_ttl=lease_ttl
                )
        replica_a, replica_b = (call.args[0] for call in schedule_lib.every.return_value.seconds.do.call_args_list)

        counts: list[int] = []
        for _ in range(TICKS):
            tick_start = frozen.time_to_freeze
            before = len(runs)
            replica_a()
            frozen.move_to(tick_start + timedelta(seconds=replica_gap_seconds))
            replica_b()
            counts.append(len(runs) - before)
            frozen.move_to(tick_start + every)
    return counts


def _without_hold() -> Callable[..., Any]:
    def run_releasing_at_end(lease_store: LeaseStore, name: str, job: Callable[[], None], **_: Any) -> None:
        run_if_leased(lease_store, name, job)

    return run_releasing_at_end


def test_a_short_job_runs_once_per_tick_across_two_replicas(schedule_lib: MagicMock) -> None:
    counts = _runs_per_tick(schedule_lib, every=timedelta(minutes=5), lease_ttl=timedelta(minutes=30), replica_gap_seconds=1)

    assert counts == [1] * TICKS


def test_the_incident_upgrade_shape_runs_once_per_tick(schedule_lib: MagicMock) -> None:
    """Interval 30 min, TTL 900 s (hold 900 s), the second replica 0.7 s behind."""
    counts = _runs_per_tick(schedule_lib, every=timedelta(minutes=30), lease_ttl=timedelta(seconds=900), replica_gap_seconds=0.7)

    assert counts == [1] * TICKS


def test_control_without_the_hold_runs_twice_per_tick(schedule_lib: MagicMock) -> None:
    """Releasing at job end lets the replica a second behind run the same tick again."""
    with patch("jobs.scheduled_tasks.run_if_leased", _without_hold()):
        counts = _runs_per_tick(schedule_lib, every=timedelta(minutes=5), lease_ttl=timedelta(minutes=30), replica_gap_seconds=1)

    assert counts == [2] * TICKS
