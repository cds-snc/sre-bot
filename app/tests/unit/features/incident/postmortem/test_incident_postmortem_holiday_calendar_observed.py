"""Reading observed federal holidays through the Canada Holidays HolidayCalendar adapter.

The adapter is given a client factory returning an ``httpx.AsyncClient`` over an
``httpx.MockTransport`` that answers as the Canada Holidays API does
(``holidays?federal=true&year=Y`` with each holiday's ``observedDate``) and
records each request; nothing reaches the network. Every year the caller asks
for is one request, a holiday's observed date (not its calendar date) is
returned, and a failure or an answer of the wrong shape is a classified result,
never an empty set read as "no holidays".
"""

from collections.abc import Callable
from datetime import date
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from features.incident.postmortem.adapters import canada_holidays
from features.incident.postmortem.adapters.canada_holidays import CanadaHolidaysCalendar

pytestmark = pytest.mark.unit

BASE_URL = "https://holidays.example.test/api/v1"


def _year(year: int) -> dict[str, Any]:
    return {
        "holidays": [
            {"date": f"{year}-07-01", "observedDate": f"{year}-07-01", "nameEn": "Canada Day"},
            {"date": f"{year}-12-26", "observedDate": f"{year}-12-28", "nameEn": "Boxing Day"},
        ]
    }


def _calendar(answer: Callable[[httpx.Request], httpx.Response], requests: list[httpx.Request]) -> CanadaHolidaysCalendar:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return answer(request)

    return CanadaHolidaysCalendar(
        client_factory=lambda: httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    )


def _by_year(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=_year(int(request.url.params["year"])))


async def test_each_year_is_one_request_and_observed_dates_are_returned() -> None:
    requests: list[httpx.Request] = []

    result = await _calendar(_by_year, requests).observed_federal_holidays({2027, 2026})

    assert result.status is OperationStatus.SUCCESS
    assert result.data == frozenset({date(2026, 7, 1), date(2026, 12, 28), date(2027, 7, 1), date(2027, 12, 28)})
    assert [(r.url.path, dict(r.url.params)) for r in requests] == [
        ("/api/v1/holidays", {"federal": "true", "year": "2026"}),
        ("/api/v1/holidays", {"federal": "true", "year": "2027"}),
    ]


async def test_no_year_is_no_holiday_without_a_request() -> None:
    requests: list[httpx.Request] = []

    result = await _calendar(_by_year, requests).observed_federal_holidays(())

    assert (result.status, result.data, requests) == (OperationStatus.SUCCESS, frozenset(), [])


async def test_a_year_without_holidays_is_an_empty_set() -> None:
    result = await _calendar(lambda _: httpx.Response(200, json={"holidays": []}), []).observed_federal_holidays({2026})

    assert result.data == frozenset()


@pytest.mark.parametrize(
    "body",
    [
        {"holidays": [{"date": "2026-07-01"}]},
        {"holidays": [{"observedDate": "July first"}]},
        {"holidays": "none"},
        {"provinces": []},
        ["not", "an", "object"],
    ],
    ids=["missing_observed_date", "bad_date", "holidays_not_a_list", "no_holidays_key", "not_an_object"],
)
async def test_an_answer_of_the_wrong_shape_is_an_invalid_response(body: object) -> None:
    result = await _calendar(lambda _: httpx.Response(200, json=body), []).observed_federal_holidays({2026})

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INVALID_RESPONSE


async def test_a_body_that_is_not_json_is_an_invalid_response() -> None:
    result = await _calendar(lambda _: httpx.Response(200, text="<html>"), []).observed_federal_holidays({2026})

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INVALID_RESPONSE)


async def test_a_server_error_is_transient_and_not_an_empty_set() -> None:
    result = await _calendar(lambda _: httpx.Response(503), []).observed_federal_holidays({2026})

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.data is None


async def test_a_timeout_is_transient() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    result = await _calendar(slow, []).observed_federal_holidays({2026})

    assert (result.status, result.error_code) == (OperationStatus.TRANSIENT_ERROR, ErrorCode.TIMEOUT)


async def test_without_a_tenant_the_calendar_is_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default factory reads the slice: no [canada_holidays.tenant] is a configuration error naming the key."""
    monkeypatch.setattr(canada_holidays, "get_canada_holidays_settings", lambda: SimpleNamespace(tenant=None))

    result = await CanadaHolidaysCalendar().observed_federal_holidays({2026})

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    assert result.message is not None and "canada_holidays.tenant" in result.message
