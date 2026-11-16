"""Tests for ``classify_opsgenie_error``: each expected httpx and body-parse failure family maps
onto the closed status set, and anything else propagates.

httpx error objects and a ``json.JSONDecodeError`` are constructed directly; nothing reaches the
network.
"""

import json

import httpx
import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.opsgenie.client import classify_opsgenie_error

pytestmark = pytest.mark.unit

_REQUEST = httpx.Request("GET", "https://api.opsgenie.com/v2/schedules/s/on-calls")


def _status_error(status_code: int, headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    response = httpx.Response(status_code=status_code, headers=headers or {}, request=_REQUEST)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=_REQUEST, response=response)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, (OperationStatus.UNAUTHORIZED, ErrorCode.UNAUTHENTICATED, None)),
        (403, (OperationStatus.UNAUTHORIZED, ErrorCode.FORBIDDEN, None)),
        (404, (OperationStatus.NOT_FOUND, ErrorCode.NOT_FOUND, None)),
        (500, (OperationStatus.TRANSIENT_ERROR, ErrorCode.SERVER_ERROR, None)),
        (503, (OperationStatus.TRANSIENT_ERROR, ErrorCode.SERVER_ERROR, None)),
        (400, (OperationStatus.PERMANENT_ERROR, ErrorCode.HTTP_ERROR, None)),
        (418, (OperationStatus.PERMANENT_ERROR, ErrorCode.HTTP_ERROR, None)),
    ],
)
def test_http_status_families(status_code: int, expected: tuple[OperationStatus, str, None]) -> None:
    assert classify_opsgenie_error(_status_error(status_code)) == expected


@pytest.mark.parametrize(
    ("headers", "retry_after"),
    [
        ({"Retry-After": "42"}, 42),
        ({}, None),
        ({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None),
    ],
)
def test_rate_limited_carries_retry_after_seconds_when_sent(headers: dict[str, str], retry_after: int | None) -> None:
    """Opsgenie documents 429 and X-RateLimit-State, not Retry-After, so an absent header is None."""
    assert classify_opsgenie_error(_status_error(429, headers)) == (
        OperationStatus.TRANSIENT_ERROR,
        ErrorCode.RATE_LIMITED,
        retry_after,
    )


def test_a_timeout_is_transient() -> None:
    assert classify_opsgenie_error(httpx.ReadTimeout("slow", request=_REQUEST)) == (
        OperationStatus.TRANSIENT_ERROR,
        ErrorCode.TIMEOUT,
        None,
    )


def test_a_connection_failure_is_transient() -> None:
    assert classify_opsgenie_error(httpx.ConnectError("refused", request=_REQUEST)) == (
        OperationStatus.TRANSIENT_ERROR,
        ErrorCode.CONNECTION_ERROR,
        None,
    )


def test_an_unparseable_body_is_a_permanent_invalid_response() -> None:
    """A body that is not JSON is an expected vendor outcome (outbound-clients.md), not a bug."""
    exc = json.JSONDecodeError("Expecting value", "<html>", 0)

    assert classify_opsgenie_error(exc) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INVALID_RESPONSE, None)


def test_an_unexpected_exception_propagates() -> None:
    with pytest.raises(KeyError):
        classify_opsgenie_error(KeyError("data"))
