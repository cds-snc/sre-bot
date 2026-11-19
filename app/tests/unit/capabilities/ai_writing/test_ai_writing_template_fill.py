"""Tests for the template fill operation over the in-memory writer.

The fake's ``write`` answers a literal model output (or a scripted error), and ``fill_template``
runs the capability's real request building and parsing over it. Logged events are read with
structlog's capture_logs to check they carry the answer's shape and never its text.
"""

import pytest
from structlog.testing import capture_logs

from capabilities.ai_writing.adapters.in_memory import InMemoryAIWriter
from capabilities.ai_writing.api import FilledTemplate, TemplateAnswer, TemplateField, TemplateSection
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus

pytestmark = pytest.mark.unit

_SECTIONS = (TemplateSection("Trigger", "What began it?"), TemplateSection("Impact", "Who was affected?"))
_SECRET = "the source mentions a secret customer"


async def _fill(raw: str, **kwargs: object):
    writer = InMemoryAIWriter(respond=lambda source, instructions: raw)
    kwargs.setdefault("max_output_tokens", 900)
    result = await writer.fill_template(_SECRET, sections=_SECTIONS, instructions="Answer in JSON.", **kwargs)  # type: ignore[arg-type]
    return writer, result


async def test_a_complete_answer_fills_every_section_and_field() -> None:
    _, result = await _fill(
        '{"Trigger": "A deploy.", "Impact": "Checkout.", "On-call": "Ada"}', fields=(TemplateField("On-call"),)
    )

    assert result.status is OperationStatus.SUCCESS
    assert result.data == FilledTemplate(
        sections=(TemplateAnswer("Trigger", "A deploy."), TemplateAnswer("Impact", "Checkout.")),
        fields=(TemplateAnswer("On-call", "Ada"),),
        truncated=False,
    )


async def test_the_budget_temperature_and_instructions_reach_the_writer() -> None:
    writer, _ = await _fill('{"Trigger": "A deploy."}', max_output_tokens=4000, temperature=0.2)

    (call,) = writer.calls
    assert (call.instructions, call.max_output_tokens, call.temperature) == ("Answer in JSON.", 4000, 0.2)
    assert call.source.startswith("Template sections:\n\n### Trigger")
    assert call.source.endswith(_SECRET)


async def test_a_cut_off_answer_is_a_truncated_success_logged_as_shape() -> None:
    with capture_logs() as events:
        _, result = await _fill('{"Trigger": "A deploy.", "Impact": "Check')

    assert result.status is OperationStatus.SUCCESS
    assert result.data is not None
    assert result.data.truncated is True
    assert result.data.sections == (TemplateAnswer("Trigger", "A deploy."), TemplateAnswer("Impact", ""))
    (salvaged,) = [e for e in events if e["event"] == "ai_writing_fill_truncated_salvaged"]
    assert (salvaged["key_count"], salvaged["section_count"]) == (1, 2)
    (coverage,) = [e for e in events if e["event"] == "ai_writing_fill_coverage"]
    assert coverage["blank_sections"] == ("Impact",)


@pytest.mark.parametrize("raw", ["", "Sorry, I cannot help with the secret customer.", '["x"]'])
async def test_an_unusable_answer_is_a_permanent_unparseable_error(raw: str) -> None:
    with capture_logs() as events:
        _, result = await _fill(raw)

    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.AI_WRITING_UNPARSEABLE)
    (event,) = [e for e in events if e["event"] == "ai_writing_fill_unparseable"]
    assert event["raw_length"] == len(raw)


async def test_no_event_carries_source_or_model_text() -> None:
    with capture_logs() as events:
        await _fill('{"Trigger": "secret customer down", "Stray": "secret', fields=(TemplateField("On-call"),))
        await _fill("the secret customer is down")

    assert events
    assert not [e for e in events if "secret" in repr(e)]


async def test_a_write_error_passes_through_classified() -> None:
    scripted = OperationResult.transient_error(message="busy", error_code=ErrorCode.RATE_LIMITED, retry_after=30.0)
    writer = InMemoryAIWriter(result=scripted)

    result = await writer.fill_template("s", sections=_SECTIONS, instructions="i", max_output_tokens=50)

    assert (result.status, result.error_code, result.retry_after) == (
        OperationStatus.TRANSIENT_ERROR,
        ErrorCode.RATE_LIMITED,
        30.0,
    )
