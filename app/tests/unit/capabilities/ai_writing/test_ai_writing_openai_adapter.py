"""Tests for the OpenAI adapter of the AI writing capability.

No live network calls: the adapter's vendor-client factory is replaced at the edge by an httpx
client over a MockTransport serving canned responses, so the real request, response and
raise_for_status path runs offline. Logged events are read with structlog's capture_logs.
"""

import json
from collections.abc import Callable
from unittest.mock import patch

import httpx
import pytest
from structlog.testing import capture_logs

from capabilities.ai_writing.adapters.openai import OpenAIWriter
from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from integrations.openai.settings import OpenAISettings
from tests.unit.capabilities.ai_writing.conftest import MODEL

pytestmark = pytest.mark.unit

_CLIENT = "capabilities.ai_writing.adapters.openai.build_openai_client"
type Handler = Callable[[httpx.Request], httpx.Response]
_BUDGET = 1234


def _mock_client(handler: Handler, settings: OpenAISettings) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=settings.base_url, transport=httpx.MockTransport(handler))


def _completion(content: str, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]})


async def _write(settings: OpenAISettings, handler: Handler, **kwargs: object):
    kwargs.setdefault("max_output_tokens", _BUDGET)
    with patch(_CLIENT, return_value=_mock_client(handler, settings)):
        return await OpenAIWriter(settings=settings, model=MODEL).write("transcript", instructions="Be terse.", **kwargs)  # type: ignore[arg-type]


def test_a_configured_adapter_is_available(openai_settings: OpenAISettings) -> None:
    assert OpenAIWriter(settings=openai_settings, model=MODEL).is_available() is True


async def test_success_returns_the_stripped_text_from_the_completions_endpoint(openai_settings: OpenAISettings) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.read().decode())
        return _completion("  A concise summary.  ")

    with patch(_CLIENT, return_value=_mock_client(handler, openai_settings)):
        result = await OpenAIWriter(settings=openai_settings, model=MODEL).write(
            "alice: prod is down", instructions="Be terse.", max_output_tokens=_BUDGET
        )

    assert (result.status, result.data) == (OperationStatus.SUCCESS, "A concise summary.")
    assert captured["url"].endswith("/chat/completions")
    assert captured["body"]["model"] == MODEL
    assert captured["body"]["messages"] == [
        {"role": "system", "content": "Be terse."},
        {"role": "user", "content": "alice: prod is down"},
    ]


async def test_the_budget_the_call_sets_is_sent(openai_settings: OpenAISettings) -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.read().decode()))
        return _completion("ok")

    await _write(openai_settings, handler, max_output_tokens=3000)
    await _write(openai_settings, handler, max_output_tokens=4000)

    assert [body["max_completion_tokens"] for body in bodies] == [3000, 4000]


async def test_empty_choices_return_empty_text(openai_settings: OpenAISettings) -> None:
    with capture_logs() as logs:
        result = await _write(openai_settings, lambda request: httpx.Response(200, json={"choices": []}))

    assert (result.status, result.data) == (OperationStatus.SUCCESS, "")
    assert "openai_write_empty_content" in [entry["event"] for entry in logs]


async def test_a_truncated_completion_is_logged_with_its_budget(openai_settings: OpenAISettings) -> None:
    with capture_logs() as logs:
        result = await _write(openai_settings, lambda request: _completion("cut off", "length"))

    assert result.data == "cut off"
    (truncated,) = [entry for entry in logs if entry["event"] == "openai_write_truncated"]
    assert truncated["max_completion_tokens"] == _BUDGET


async def test_an_http_error_is_classified(openai_settings: OpenAISettings) -> None:
    result = await _write(openai_settings, lambda request: httpx.Response(401, json={"error": "bad key"}))

    assert (result.status, result.error_code, result.retry_after) == (
        OperationStatus.UNAUTHORIZED,
        ErrorCode.UNAUTHENTICATED,
        None,
    )


async def test_a_rate_limit_is_transient_with_its_retry_after(openai_settings: OpenAISettings) -> None:
    result = await _write(openai_settings, lambda request: httpx.Response(429, headers={"Retry-After": "7"}))

    assert (result.status, result.error_code, result.retry_after) == (
        OperationStatus.TRANSIENT_ERROR,
        ErrorCode.RATE_LIMITED,
        7,
    )


async def test_an_unparseable_body_is_a_permanent_invalid_response(openai_settings: OpenAISettings) -> None:
    with capture_logs() as logs:
        result = await _write(openai_settings, lambda request: httpx.Response(200, text="<html>gateway page</html>"))

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.INVALID_RESPONSE)
    assert "openai_write_failed" in [entry["event"] for entry in logs]


class TestTemperature:
    """Temperature is the caller's: omitted unless the call sets one, since some models reject it."""

    @staticmethod
    async def _payload_for(settings: OpenAISettings, **kwargs: object) -> dict:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.read().decode())
            return _completion("a summary")

        await _write(settings, handler, **kwargs)
        return captured["body"]

    async def test_temperature_is_omitted_when_the_call_sets_none(self, openai_settings: OpenAISettings) -> None:
        """The gateway's model rejects the parameter with a 400."""
        assert "temperature" not in await self._payload_for(openai_settings)

    @pytest.mark.parametrize("temperature", [0.0, 0.7])
    async def test_a_temperature_the_call_sets_is_sent(self, openai_settings: OpenAISettings, temperature: float) -> None:
        assert (await self._payload_for(openai_settings, temperature=temperature))["temperature"] == temperature


class TestErrorDiagnostics:
    """A 400 must say what the API objected to, not just that it objected."""

    async def test_the_error_body_and_sent_parameters_are_logged(self, openai_settings: OpenAISettings) -> None:
        body = '{"error": {"message": "Unsupported parameter: temperature", "param": "temperature"}}'

        with capture_logs() as logs:
            result = await _write(openai_settings, lambda request: httpx.Response(400, text=body), temperature=0.0)

        assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.HTTP_ERROR)
        (failed,) = [entry for entry in logs if entry["event"] == "openai_write_failed"]
        assert "Unsupported parameter: temperature" in failed["response_body"]
        assert "temperature" in failed["sent_parameters"]

    async def test_a_failure_without_a_response_still_logs_cleanly(self, openai_settings: OpenAISettings) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route to host")

        with capture_logs() as logs:
            result = await _write(openai_settings, handler)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        (failed,) = [entry for entry in logs if entry["event"] == "openai_write_failed"]
        assert failed["response_body"] == ""
