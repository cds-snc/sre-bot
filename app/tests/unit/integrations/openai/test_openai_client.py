"""Tests for the OpenAI vendor client: authenticated client construction and
error classification.

No live network calls: httpx error responses are constructed directly, and the
factory's transport is observed through a recording stand-in for
``httpx.AsyncHTTPTransport`` (the SDK edge), so the assertions read the resilience
settings the client is built with rather than httpx internals.
"""

from typing import Any

import httpx
import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.openai.client import build_openai_client, classify_openai_error
from integrations.openai.settings import OpenAISettings

pytestmark = pytest.mark.unit


def _http_status_error(status_code: int, headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(status_code=status_code, headers=headers or {}, request=request)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


class TestBuildOpenAIClient:
    def test_sets_auth_header_and_base_url(self, openai_settings: OpenAISettings) -> None:
        client = build_openai_client(settings=openai_settings)

        assert client.headers["Authorization"] == "Bearer sk-test-key"
        assert client.headers["Content-Type"] == "application/json"
        assert str(client.base_url).rstrip("/") == openai_settings.base_url

    def test_sets_explicit_timeout_and_connect_retries(
        self, openai_settings: OpenAISettings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The retry policy is set once, at construction, beside the timeout (outbound-clients.md)."""
        built: list[dict[str, Any]] = []
        real_transport = httpx.AsyncHTTPTransport

        def recording_transport(**kwargs: Any) -> httpx.AsyncHTTPTransport:
            built.append(kwargs)
            return real_transport(**kwargs)

        monkeypatch.setattr(httpx, "AsyncHTTPTransport", recording_transport)
        settings = openai_settings.model_copy(update={"connect_retries": 3, "timeout_seconds": 42.0})

        client = build_openai_client(settings=settings)

        assert built == [{"retries": 3}]
        assert client.timeout == httpx.Timeout(42.0)


class TestClassifyOpenAIError:
    @pytest.mark.parametrize(
        ("status_code", "expected"),
        [
            (401, (OperationStatus.UNAUTHORIZED, ErrorCode.UNAUTHENTICATED, None)),
            (403, (OperationStatus.UNAUTHORIZED, ErrorCode.FORBIDDEN, None)),
            (404, (OperationStatus.NOT_FOUND, ErrorCode.NOT_FOUND, None)),
            (500, (OperationStatus.TRANSIENT_ERROR, ErrorCode.SERVER_ERROR, None)),
            (503, (OperationStatus.TRANSIENT_ERROR, ErrorCode.SERVER_ERROR, None)),
            (400, (OperationStatus.PERMANENT_ERROR, ErrorCode.HTTP_ERROR, None)),
            (422, (OperationStatus.PERMANENT_ERROR, ErrorCode.HTTP_ERROR, None)),
        ],
    )
    def test_http_status_families(self, status_code: int, expected: tuple[OperationStatus, str, None]) -> None:
        assert classify_openai_error(_http_status_error(status_code)) == expected

    @pytest.mark.parametrize(
        ("headers", "retry_after"),
        [
            ({"Retry-After": "42"}, 42),
            ({"Retry-After": "0"}, 0),
            ({}, None),
            ({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None),
        ],
    )
    def test_rate_limited_carries_numeric_retry_after_only(self, headers: dict[str, str], retry_after: int | None) -> None:
        """Only a delay in seconds is passed on; an absent or HTTP-date header gives None, as Google's classifier does."""
        assert classify_openai_error(_http_status_error(429, headers=headers)) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.RATE_LIMITED,
            retry_after,
        )

    def test_timeout_is_transient(self) -> None:
        assert classify_openai_error(httpx.ReadTimeout("timed out")) == (OperationStatus.TRANSIENT_ERROR, ErrorCode.TIMEOUT, None)

    def test_other_transport_error_is_a_transient_connection_error(self) -> None:
        assert classify_openai_error(httpx.ConnectError("connection refused")) == (
            OperationStatus.TRANSIENT_ERROR,
            ErrorCode.CONNECTION_ERROR,
            None,
        )

    def test_unmapped_exception_propagates(self) -> None:
        with pytest.raises(KeyError):
            classify_openai_error(KeyError("bug"))
