"""Tests for ``classify_notify_error``: each expected httpx and body-parse failure family maps
onto the closed status set, and anything else propagates.

httpx error objects and a ``json.JSONDecodeError`` are constructed directly; nothing reaches the
network.
"""

import json

import httpx
import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.notify.client import classify_notify_error

pytestmark = pytest.mark.unit

_REQUEST = httpx.Request("POST", "https://notify.example.test/sre-tools/api-key-revoke")


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
    """Notify's 400 for an invalid revocation payload is permanent; 5xx is worth a later retry."""
    assert classify_notify_error(_status_error(status_code)) == expected


@pytest.mark.parametrize(
    ("headers", "retry_after"),
    [
        ({"Retry-After": "42"}, 42),
        ({}, None),
        ({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None),
    ],
)
def test_rate_limited_carries_retry_after_seconds_when_sent(headers: dict[str, str], retry_after: int | None) -> None:
    assert classify_notify_error(_status_error(429, headers)) == (
        OperationStatus.TRANSIENT_ERROR,
        ErrorCode.RATE_LIMITED,
        retry_after,
    )


def test_a_timeout_is_transient() -> None:
    exc = httpx.ReadTimeout("read timed out", request=_REQUEST)

    assert classify_notify_error(exc) == (OperationStatus.TRANSIENT_ERROR, ErrorCode.TIMEOUT, None)


def test_a_connection_failure_is_transient() -> None:
    exc = httpx.ConnectError("connection refused", request=_REQUEST)

    assert classify_notify_error(exc) == (OperationStatus.TRANSIENT_ERROR, ErrorCode.CONNECTION_ERROR, None)


def test_an_unparseable_body_is_an_invalid_response() -> None:
    exc = json.JSONDecodeError("Expecting value", "<html>", 0)

    assert classify_notify_error(exc) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INVALID_RESPONSE, None)


def test_an_unexpected_exception_propagates() -> None:
    """A KeyError is a bug, not an outcome: it is never turned into a status."""
    with pytest.raises(KeyError):
        classify_notify_error(KeyError("token"))
