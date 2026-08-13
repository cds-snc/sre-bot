"""Tests for the OpenAI vendor client: authenticated client construction and
error classification.

No live network calls -- httpx error responses are constructed directly.
"""

from __future__ import annotations

import httpx
import pytest

from infrastructure.operations.status import OperationStatus
from integrations.openai.client import build_openai_client, classify_openai_error

pytestmark = pytest.mark.unit


def _http_status_error(
    status_code: int, headers: dict[str, str] | None = None
) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(
        status_code=status_code, headers=headers or {}, request=request
    )
    return httpx.HTTPStatusError(
        f"HTTP {status_code}", request=request, response=response
    )


class TestBuildOpenAIClient:
    def test_sets_auth_header_and_base_url(self, openai_settings):
        client = build_openai_client(settings=openai_settings)

        assert client.headers["Authorization"] == "Bearer sk-test-key"
        assert client.headers["Content-Type"] == "application/json"
        assert str(client.base_url).rstrip("/") == openai_settings.BASE_URL


class TestClassifyOpenAIError:
    def test_unauthorized(self):
        result = classify_openai_error(_http_status_error(401))

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "UNAUTHORIZED"

    def test_forbidden(self):
        result = classify_openai_error(_http_status_error(403))

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "FORBIDDEN"

    def test_not_found(self):
        result = classify_openai_error(_http_status_error(404))

        assert result.status == OperationStatus.NOT_FOUND
        assert result.error_code == "NOT_FOUND"

    def test_rate_limited_with_retry_after(self):
        result = classify_openai_error(
            _http_status_error(429, headers={"Retry-After": "42"})
        )

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "RATE_LIMITED"
        assert result.retry_after == 42

    def test_rate_limited_default_retry_after(self):
        result = classify_openai_error(_http_status_error(429))

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.retry_after == 60

    def test_server_error_is_transient(self):
        result = classify_openai_error(_http_status_error(503))

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "SERVER_ERROR"

    def test_other_4xx_is_permanent(self):
        result = classify_openai_error(_http_status_error(400))

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "HTTP_ERROR"

    def test_timeout_is_transient(self):
        result = classify_openai_error(httpx.TimeoutException("timed out"))

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "TIMEOUT"

    def test_connection_error_is_transient(self):
        result = classify_openai_error(httpx.ConnectError("connection refused"))

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CONNECTION_ERROR"

    def test_unmapped_exception_propagates(self):
        with pytest.raises(KeyError):
            classify_openai_error(KeyError("bug"))
