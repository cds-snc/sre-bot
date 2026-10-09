"""Tests for binding the status-update ``TextGenerator`` to the OpenAI summarizer.

``get_summarizer`` is patched in the adapter module: once with a sentinel to
show a configured integration is used as is, and once with a pydantic
``ValidationError`` side effect, which is what loading the OpenAI settings
raises when the API key is missing. The unconfigured case must return a
generator whose call is a classified error, so drafting falls back instead of
crashing.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError
from structlog.testing import capture_logs

from contracts.operations import OperationStatus
from packages.incident.scribe.adapters.text_generation import (
    TEXT_GENERATION_UNAVAILABLE_CODE,
    build_status_update_text_generator,
)
from packages.incident.scribe.ports import TextGenerator

pytestmark = pytest.mark.unit

_TARGET = "packages.incident.scribe.adapters.text_generation.get_summarizer"


class _RequiredKey(BaseModel):
    api_key: str


def _missing_key_error() -> ValidationError:
    try:
        _RequiredKey.model_validate({})
    except ValidationError as error:
        return error
    raise AssertionError("validation unexpectedly passed")


def test_a_configured_integration_returns_the_process_summarizer() -> None:
    """With settings that load, the OpenAI summarizer is the generator."""
    summarizer = MagicMock()

    with patch(_TARGET, return_value=summarizer):
        assert build_status_update_text_generator() is summarizer


@pytest.mark.asyncio
async def test_unloadable_settings_give_a_generator_that_reports_unavailable() -> None:
    """A missing key is an outcome, not a crash: the call returns the unavailable code, and the log names fields, never values."""
    with patch(_TARGET, side_effect=_missing_key_error()), capture_logs() as logs:
        generator = build_status_update_text_generator()

    assert isinstance(generator, TextGenerator)
    result = await generator.summarize("transcript", instructions="x", max_output_tokens=10)
    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, TEXT_GENERATION_UNAVAILABLE_CODE)
    (logged,) = logs
    assert (logged["event"], logged["fields"]) == ("incident_status_update_text_generation_unconfigured", ["api_key"])
