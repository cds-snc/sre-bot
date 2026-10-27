"""Tests for binding the status-update ``TextGenerator`` to the OpenAI summarizer.

The adapter module's ``get_openai_settings`` is patched with a stand-in slice, once with a
tenant entry and once without (OpenAI not configured), and ``get_summarizer`` with a
sentinel. Text generation is a designed optional dependency of comms: with no tenant the
generator's call is a classified error, so drafting falls back to writing by hand, and the
summarizer is never built.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationStatus
from features.incident.comms.adapters.text_generation import (
    TEXT_GENERATION_UNAVAILABLE_CODE,
    build_status_update_text_generator,
)
from features.incident.comms.ports import TextGenerator

pytestmark = pytest.mark.unit

_MODULE = "features.incident.comms.adapters.text_generation"


def test_a_configured_integration_returns_the_process_summarizer() -> None:
    """With a tenant entry, the OpenAI summarizer is the generator."""
    summarizer = MagicMock()

    with (
        patch(f"{_MODULE}.get_openai_settings", return_value=SimpleNamespace(tenant=object())),
        patch(f"{_MODULE}.get_summarizer", return_value=summarizer),
    ):
        assert build_status_update_text_generator() is summarizer


@pytest.mark.asyncio
async def test_no_tenant_gives_a_generator_that_reports_unavailable() -> None:
    """OpenAI not configured is an outcome, not a crash: the call returns the unavailable code."""
    with (
        patch(f"{_MODULE}.get_openai_settings", return_value=SimpleNamespace(tenant=None)),
        patch(f"{_MODULE}.get_summarizer") as get_summarizer,
        capture_logs() as logs,
    ):
        generator = build_status_update_text_generator()

    get_summarizer.assert_not_called()
    assert isinstance(generator, TextGenerator)
    result = await generator.summarize("transcript", instructions="x", max_output_tokens=10)
    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, TEXT_GENERATION_UNAVAILABLE_CODE)
    (logged,) = logs
    assert logged["event"] == "incident_status_update_text_generation_unconfigured"
