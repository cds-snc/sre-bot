"""One behaviour suite for every HolidayCalendar: the Canada Holidays adapter and the in-memory fake.

The adapter reads an ``httpx.MockTransport`` answering as the Canada Holidays
API for the holidays below; the fake is built with the same dates. Each test
runs against both, so a consumer tested on the fake sees the adapter's rules:
only the asked years' observed dates, and a failure is a result, never an
empty set.
"""

from collections.abc import Callable
from datetime import date

import httpx
import pytest

from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from features.incident.postmortem.adapters.canada_holidays import CanadaHolidaysCalendar
from features.incident.postmortem.adapters.in_memory import InMemoryHolidayCalendar
from features.incident.postmortem.interfaces import HolidayCalendar

pytestmark = pytest.mark.unit

HOLIDAYS = {date(2026, 7, 1), date(2026, 12, 28), date(2027, 7, 1)}


def _adapter(fail: bool) -> HolidayCalendar:
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(503)
        year = int(request.url.params["year"])
        observed = [{"observedDate": day.isoformat()} for day in sorted(HOLIDAYS) if day.year == year]
        return httpx.Response(200, json={"holidays": observed})

    return CanadaHolidaysCalendar(
        client_factory=lambda: httpx.AsyncClient(base_url="https://h.example.test/api/v1", transport=httpx.MockTransport(handler))
    )


def _fake(fail: bool) -> HolidayCalendar:
    return InMemoryHolidayCalendar(HOLIDAYS, fail_with=OperationResult.transient_error("unavailable") if fail else None)


@pytest.fixture(params=[_adapter, _fake], ids=["canada_holidays", "in_memory"])
def build(request: pytest.FixtureRequest) -> Callable[[bool], HolidayCalendar]:
    return request.param  # type: ignore[no-any-return]


def test_both_satisfy_the_protocol(build: Callable[[bool], HolidayCalendar]) -> None:
    assert isinstance(build(False), HolidayCalendar)


async def test_only_the_asked_years_are_returned(build: Callable[[bool], HolidayCalendar]) -> None:
    result = await build(False).observed_federal_holidays({2026})

    assert result.data == frozenset({date(2026, 7, 1), date(2026, 12, 28)})


async def test_several_years_are_merged(build: Callable[[bool], HolidayCalendar]) -> None:
    result = await build(False).observed_federal_holidays([2026, 2027])

    assert result.data == frozenset(HOLIDAYS)


async def test_a_failure_is_a_result_not_an_empty_set(build: Callable[[bool], HolidayCalendar]) -> None:
    result = await build(True).observed_federal_holidays({2026})

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.data is None
