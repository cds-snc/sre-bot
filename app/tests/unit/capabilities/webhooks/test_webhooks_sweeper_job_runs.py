"""Unit tests for the inbox sweeper job: its registration and one run.

The registry is a recording stand-in for the scheduler's; the composition-root factories the
job calls are monkeypatched to record on which event loop they were built and whether their
clients were closed. The sweep itself is covered by the processor tests.
"""

import asyncio
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import pytest

from capabilities.webhooks.entrypoints import jobs

pytestmark = pytest.mark.unit


class _Scopes:
    def __init__(self) -> None:
        self.opened = 0

    @contextmanager
    def create_scope(self) -> Iterator[object]:
        self.opened += 1
        yield object()


class _Registry:
    def __init__(self) -> None:
        self.scopes = _Scopes()
        self.intervals: list[dict[str, Any]] = []

    @property
    def service_scopes(self) -> _Scopes:
        return self.scopes

    def register_interval(
        self, *, job_name: str, every: timedelta, job: Callable[[], None], lease_ttl: timedelta | None = None
    ) -> None:
        self.intervals.append({"job_name": job_name, "every": every, "job": job, "lease_ttl": lease_ttl})


def test_the_sweeper_registers_as_a_leased_interval_job_from_its_settings() -> None:
    registry = _Registry()

    jobs.register_sweeper(registry)

    (registered,) = registry.intervals
    assert registered["job_name"] == "webhooks_inbox_sweeper"
    assert (registered["every"], registered["lease_ttl"]) == (timedelta(seconds=60), timedelta(seconds=300))


class _Sns:
    def __init__(self, loops: list[object]) -> None:
        loops.append(asyncio.get_running_loop())
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def test_a_run_builds_its_clients_inside_its_own_loop_and_closes_them(monkeypatch: pytest.MonkeyPatch) -> None:
    loops: list[object] = []
    built: list[_Sns] = []
    swept: list[object] = []

    def build_sns() -> _Sns:
        sns = _Sns(loops)
        built.append(sns)
        return sns

    class _Processor:
        async def sweep(self) -> int:
            swept.append(asyncio.get_running_loop())
            return 3

    monkeypatch.setattr(jobs, "build_sns_http", build_sns)
    monkeypatch.setattr(jobs, "build_channel_posters", lambda: {})
    monkeypatch.setattr(jobs, "build_processor", lambda services, **kwargs: _Processor())
    scopes = _Scopes()

    jobs.run_sweeper(scopes)
    jobs.run_sweeper(scopes)

    assert scopes.opened == 2
    assert loops == swept and loops[0] is not loops[1], "each run has its own loop and builds its clients on it"
    assert all(sns.closed for sns in built)


def test_a_failed_sweep_still_closes_its_client_and_reaches_the_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[_Sns] = []

    class _Failing:
        async def sweep(self) -> int:
            raise RuntimeError("store down")

    monkeypatch.setattr(jobs, "build_sns_http", lambda: built.append(_Sns([])) or built[-1])
    monkeypatch.setattr(jobs, "build_channel_posters", lambda: {})
    monkeypatch.setattr(jobs, "build_processor", lambda services, **kwargs: _Failing())

    with pytest.raises(RuntimeError):
        jobs.run_sweeper(_Scopes())

    assert built[0].closed
