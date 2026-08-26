"""Tests for the OpenAI-backed Summarizer adapter.

No live network calls -- an httpx MockTransport serves canned responses so the
real request/response/raise_for_status path is exercised offline.
"""

from __future__ import annotations

<<<<<<< HEAD
import json
=======
>>>>>>> main
from unittest.mock import patch

import httpx
import pytest

<<<<<<< HEAD
import integrations.openai.summarizer as summarizer_module
=======
>>>>>>> main
from infrastructure.operations.status import OperationStatus
from integrations.openai.summarizer import OpenAISummarizer, Summarizer

pytestmark = pytest.mark.unit


def _mock_client(handler, settings) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient wired to a MockTransport handler."""
    return httpx.AsyncClient(
        base_url=settings.BASE_URL,
        transport=httpx.MockTransport(handler),
    )


class TestOpenAISummarizer:
    def test_satisfies_summarizer_protocol(self, openai_settings):
        assert isinstance(OpenAISummarizer(settings=openai_settings), Summarizer)

    @pytest.mark.asyncio
    async def test_success_returns_summary(self, openai_settings):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["body"] = request.read().decode()
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "  A concise summary.  "}}]},
            )

        summarizer = OpenAISummarizer(settings=openai_settings)
        with patch(
            "integrations.openai.summarizer.build_openai_client",
            return_value=_mock_client(handler, openai_settings),
        ):
            result = await summarizer.summarize("alice: prod is down\nbob: on it")

        assert result.status == OperationStatus.SUCCESS
        assert result.data == "A concise summary."
        assert captured["url"].endswith("/chat/completions")
        assert "prod is down" in captured["body"]

    @pytest.mark.asyncio
    async def test_custom_instructions_are_sent(self, openai_settings):
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = request.read().decode()
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        summarizer = OpenAISummarizer(settings=openai_settings)
        with patch(
            "integrations.openai.summarizer.build_openai_client",
            return_value=_mock_client(handler, openai_settings),
        ):
            await summarizer.summarize("t", instructions="Be terse.")

        assert "Be terse." in captured["body"]

    @pytest.mark.asyncio
    async def test_empty_choices_returns_empty_summary(self, openai_settings):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"choices": []})

        summarizer = OpenAISummarizer(settings=openai_settings)
        with patch(
            "integrations.openai.summarizer.build_openai_client",
            return_value=_mock_client(handler, openai_settings),
        ):
            result = await summarizer.summarize("t")

        assert result.status == OperationStatus.SUCCESS
        assert result.data == ""

    @pytest.mark.asyncio
    async def test_http_error_is_classified(self, openai_settings):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "bad key"})

        summarizer = OpenAISummarizer(settings=openai_settings)
        with patch(
            "integrations.openai.summarizer.build_openai_client",
            return_value=_mock_client(handler, openai_settings),
        ):
            result = await summarizer.summarize("t")

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_rate_limit_is_transient(self, openai_settings):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "7"})

        summarizer = OpenAISummarizer(settings=openai_settings)
        with patch(
            "integrations.openai.summarizer.build_openai_client",
            return_value=_mock_client(handler, openai_settings),
        ):
            result = await summarizer.summarize("t")

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "RATE_LIMITED"
        assert result.retry_after == 7
<<<<<<< HEAD


class TestTemperature:
    """Drafting wants reproducibility: the same channel should draft the same."""

    @staticmethod
    def _capturing_handler(captured: dict):
        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.read().decode())
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "a summary"}, "finish_reason": "stop"}]},
            )

        return handler

    async def _payload_for(self, settings) -> dict:
        captured: dict = {}
        with patch(
            "integrations.openai.summarizer.build_openai_client",
            return_value=_mock_client(self._capturing_handler(captured), settings),
        ):
            await OpenAISummarizer(settings=settings).summarize("transcript")
        return captured["body"]

    @pytest.mark.asyncio
    async def test_temperature_is_omitted_by_default(self, openai_settings):
        """The gateway's model rejects the parameter with a 400."""
        payload = await self._payload_for(openai_settings)

        assert "temperature" not in payload

    @pytest.mark.asyncio
    async def test_zero_is_sent_when_opted_into(self, openai_settings, monkeypatch):
        monkeypatch.setattr(openai_settings, "TEMPERATURE", 0.0)

        payload = await self._payload_for(openai_settings)

        assert payload["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_a_configured_temperature_is_used(self, openai_settings, monkeypatch):
        monkeypatch.setattr(openai_settings, "TEMPERATURE", 0.7)

        payload = await self._payload_for(openai_settings)

        assert payload["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_a_negative_temperature_omits_the_parameter(self, openai_settings, monkeypatch):
        """Some models reject temperature outright, which would fail the call."""
        monkeypatch.setattr(openai_settings, "TEMPERATURE", -1.0)

        payload = await self._payload_for(openai_settings)

        assert "temperature" not in payload
        assert payload["model"] == openai_settings.MODEL


class TestErrorDiagnostics:
    """A 400 must say what the API objected to, not just that it objected."""

    @pytest.mark.asyncio
    async def test_the_error_body_and_sent_parameters_are_logged(self, openai_settings, monkeypatch):
        monkeypatch.setattr(openai_settings, "TEMPERATURE", 0.0)
        body = '{"error": {"message": "Unsupported parameter: temperature", "param": "temperature"}}'

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, text=body)

        logged: dict = {}

        def capture(event, **kwargs):
            logged.update(kwargs, event=event)

        with (
            patch(
                "integrations.openai.summarizer.build_openai_client",
                return_value=_mock_client(handler, openai_settings),
            ),
            patch.object(summarizer_module.logger, "warning", capture),
        ):
            result = await OpenAISummarizer(settings=openai_settings).summarize("transcript")

        assert result.status == OperationStatus.PERMANENT_ERROR
        # The body names the offending parameter, and we record what we sent.
        assert "Unsupported parameter: temperature" in logged["response_body"]
        assert "temperature" in logged["sent_parameters"]

    @pytest.mark.asyncio
    async def test_a_failure_without_a_response_still_logs_cleanly(self, openai_settings):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route to host")

        with patch(
            "integrations.openai.summarizer.build_openai_client",
            return_value=_mock_client(handler, openai_settings),
        ):
            result = await OpenAISummarizer(settings=openai_settings).summarize("transcript")

        assert result.status == OperationStatus.TRANSIENT_ERROR
=======
>>>>>>> main
