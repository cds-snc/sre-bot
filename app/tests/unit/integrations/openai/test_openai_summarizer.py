"""Tests for the OpenAI-backed Summarizer adapter.

No live network calls -- an httpx MockTransport serves canned responses so the
real request/response/raise_for_status path is exercised offline.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

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
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "ok"}}]}
            )

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
