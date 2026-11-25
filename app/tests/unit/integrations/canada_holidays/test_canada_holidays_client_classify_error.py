"""Tests for ``classify_canada_holidays_error``: each expected httpx and body-parse failure family
maps onto the closed status set, and anything else propagates.

httpx error objects and a ``json.JSONDecodeError`` are constructed directly; nothing reaches the
network.
"""

import json

import httpx
import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.canada_holidays.client import classify_canada_holidays_error

pytestmark = pytest.mark.unit

_REQUEST = httpx.Request("GET", "https://canada-holidays.ca/api/v1/holidays")


def _status_error(status_code: int, headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    response = httpx.Response(status_code=status_code, headers=headers or {}, request=_REQUEST)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=_REQUEST, response=response)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, (OperationStatus.UNAUTHORIZED, ErrorCode.UNAUTHENTICATED, None)),
        (403, (OperationStatus.UNAUTHORIZED, ErrorCode.FORBIDDEN, None)),
        (404, (OperationStatus.NOT_FOUND, ErrorCode.NOT_FOUND, None)),
        (429, (OperationStatus.TRANSIENT_ERROR, ErrorCode.RATE_LIMITED, None)),
        (500, (OperationStatus.TRANSIENT_ERROR, ErrorCode.SERVER_ERROR, None)),
        (503, (OperationStatus.TRANSIENT_ERROR, ErrorCode.SERVER_ERROR, None)),
        (400, (OperationStatus.PERMANENT_ERROR, ErrorCode.HTTP_ERROR, None)),
    ],
)
def test_http_statuses_map_to_the_closed_set(status_code: int, expected: tuple[OperationStatus, str, int | None]) -> None:
    assert classify_canada_holidays_error(_status_error(status_code)) == expected


def test_a_rate_limit_carries_its_retry_after_seconds() -> None:
    assert classify_canada_holidays_error(_status_error(429, {"Retry-After": "12"}))[2] == 12


def test_a_retry_after_date_is_not_a_delay() -> None:
    assert classify_canada_holidays_error(_status_error(429, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}))[2] is None


def test_a_timeout_is_transient() -> None:
    assert classify_canada_holidays_error(httpx.ReadTimeout("slow", request=_REQUEST)) == (
        OperationStatus.TRANSIENT_ERROR,
        ErrorCode.TIMEOUT,
        None,
    )


def test_a_connection_failure_is_transient() -> None:
    assert classify_canada_holidays_error(httpx.ConnectError("down", request=_REQUEST)) == (
        OperationStatus.TRANSIENT_ERROR,
        ErrorCode.CONNECTION_ERROR,
        None,
    )


def test_an_unparseable_body_is_an_invalid_response() -> None:
    assert classify_canada_holidays_error(json.JSONDecodeError("bad", "x", 0)) == (
        OperationStatus.PERMANENT_ERROR,
        ErrorCode.INVALID_RESPONSE,
        None,
    )


def test_an_unknown_exception_propagates() -> None:
    with pytest.raises(KeyError):
        classify_canada_holidays_error(KeyError("holidays"))
