"""Conformance tests for the AI writing fakes against the implementations they stand in for.

The available pair is the OpenAI adapter (its vendor-client factory replaced at the edge by an
httpx client over a MockTransport echoing the request) and the in-memory fake scripted to echo;
the unavailable pair is the unconfigured implementation and the in-memory fake with
available=False. Assertions are on the Protocol's observable rules only. The enrolment test keeps
the fake registered with the fake-coverage rule.
"""

import json
from collections.abc import Iterator
from unittest.mock import patch

import httpx
import pytest

from bin.check_fake_coverage import find_covered_protocols, find_fakes
from capabilities.ai_writing.adapters.in_memory import InMemoryAIWriter
from capabilities.ai_writing.adapters.openai import OpenAIWriter
from capabilities.ai_writing.adapters.unconfigured import UnconfiguredAIWriter
from capabilities.ai_writing.api import AIWriter
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from integrations.openai.settings import OpenAISettings

pytestmark = pytest.mark.unit


def _echo(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.read().decode())
    system, user = (message["content"] for message in body["messages"])
    return httpx.Response(200, json={"choices": [{"message": {"content": f"{system}|{user}"}, "finish_reason": "stop"}]})


@pytest.fixture(params=["openai", "in_memory"])
def available(request: pytest.FixtureRequest, openai_settings: OpenAISettings) -> Iterator[AIWriter]:
    if request.param == "in_memory":
        yield InMemoryAIWriter(respond=lambda source, instructions: f"{instructions}|{source}")
        return
    client = httpx.AsyncClient(base_url=openai_settings.base_url, transport=httpx.MockTransport(_echo))
    with patch("capabilities.ai_writing.adapters.openai.build_openai_client", return_value=client):
        yield OpenAIWriter(settings=openai_settings)


@pytest.fixture(params=["unconfigured", "in_memory"])
def unavailable(request: pytest.FixtureRequest) -> AIWriter:
    return UnconfiguredAIWriter() if request.param == "unconfigured" else InMemoryAIWriter(available=False)


async def test_an_available_writer_answers_from_the_instructions_and_the_source(available: AIWriter) -> None:
    result = await available.write("the source", instructions="the instructions", max_output_tokens=50)

    assert available.is_available() is True
    assert (result.status, result.data) == (OperationStatus.SUCCESS, "the instructions|the source")


async def test_an_unavailable_writer_reports_it_on_every_call(unavailable: AIWriter) -> None:
    result = await unavailable.write("the source", instructions="the instructions")

    assert unavailable.is_available() is False
    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.AI_WRITING_UNAVAILABLE)


async def test_the_fake_records_each_call() -> None:
    fake = InMemoryAIWriter()

    await fake.write("the source", instructions="the instructions", max_output_tokens=50)

    (call,) = fake.calls
    assert (call.source, call.instructions, call.max_output_tokens) == ("the source", "the instructions", 50)


async def test_the_fake_returns_a_scripted_result() -> None:
    scripted = OperationResult.transient_error(message="busy", error_code=ErrorCode.RATE_LIMITED, retry_after=7)

    result = await InMemoryAIWriter(result=scripted).write("s", instructions="i")

    assert result is scripted


def test_the_fake_is_enrolled_in_the_fake_coverage_rule() -> None:
    assert "capabilities/ai_writing/api.py:AIWriter" in find_covered_protocols()
    assert "AIWriter" in find_fakes()
