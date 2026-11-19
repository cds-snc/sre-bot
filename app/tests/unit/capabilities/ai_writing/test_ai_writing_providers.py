"""Tests for resolving the process AI writer from configuration.

Configuration files are installed into tmp_path (with or without an [openai.tenant] entry and an
[ai_writing] model) and the API key is set in the environment; the vendor-client factory is replaced at the edge by a
mock that must stay uncalled, since resolving a writer never reaches the endpoint. The
provider cache is cleared around each test by the package conftest.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from structlog.testing import capture_logs

from capabilities.ai_writing.adapters.openai import OpenAIWriter
from capabilities.ai_writing.api import get_ai_writer
from capabilities.ai_writing.providers import get_ai_writer_singleton
from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from tests.unit.capabilities.ai_writing.conftest import BASE_URL, MODEL, install_openai_files

pytestmark = pytest.mark.unit

_CLIENT = "capabilities.ai_writing.adapters.openai.build_openai_client"
_TENANT = f'[openai]\n[openai.tenant]\nbase_url = "{BASE_URL}"\n'
_MODEL = f'[ai_writing]\nmodel = "{MODEL}"\n'


async def test_no_tenant_gives_a_writer_that_reports_unavailable_without_a_client(tmp_path: Path) -> None:
    install_openai_files(tmp_path)

    with patch(_CLIENT) as build, capture_logs() as logs:
        writer = get_ai_writer()
        result = await writer.write("transcript", instructions="x", max_output_tokens=10)

    build.assert_not_called()
    assert writer.is_available() is False
    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.AI_WRITING_UNAVAILABLE)
    assert [entry["event"] for entry in logs] == ["ai_writing_unconfigured"]
    assert "sk-" not in repr(logs)


def test_a_tenant_and_a_model_give_the_openai_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_openai_files(tmp_path, base=_TENANT + _MODEL)
    monkeypatch.setenv("OPENAI__API_KEY", "sk-test-key")

    writer = get_ai_writer()

    assert isinstance(writer, OpenAIWriter)
    assert writer.is_available() is True


async def test_a_tenant_without_a_model_reports_unavailable_and_logs_it_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model is the organisation's value: unset, nothing is sent and the build says why."""
    install_openai_files(tmp_path, base=_TENANT + "[ai_writing]\n")
    monkeypatch.setenv("OPENAI__API_KEY", "sk-test-key")

    with patch(_CLIENT) as build, capture_logs() as logs:
        writer = get_ai_writer()
        get_ai_writer()
        result = await writer.write("transcript", instructions="x", max_output_tokens=10)

    build.assert_not_called()
    assert writer.is_available() is False
    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.AI_WRITING_UNAVAILABLE)
    assert [entry["event"] for entry in logs] == ["ai_writing_model_unset"]


def test_the_writer_is_resolved_once_per_process(tmp_path: Path) -> None:
    """Consumers ask on every modal; the configuration is read once."""
    install_openai_files(tmp_path)

    assert get_ai_writer() is get_ai_writer()
    assert get_ai_writer_singleton.cache_info().misses == 1
