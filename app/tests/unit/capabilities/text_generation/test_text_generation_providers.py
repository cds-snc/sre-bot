"""Tests for resolving the process text generator from configuration.

Configuration files are installed into tmp_path (with or without an [openai.tenant] entry) and
the API key is set in the environment; the vendor-client factory is replaced at the edge by a
mock that must stay uncalled, since resolving a generator never reaches the endpoint. The
provider cache is cleared around each test by the package conftest.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from structlog.testing import capture_logs

from capabilities.text_generation.adapters.openai import OpenAITextGenerator
from capabilities.text_generation.api import get_text_generator
from capabilities.text_generation.providers import get_text_generator_singleton
from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from tests.unit.capabilities.text_generation.conftest import BASE_URL, MODEL, install_openai_files

pytestmark = pytest.mark.unit

_CLIENT = "capabilities.text_generation.adapters.openai.build_openai_client"
_TENANT = f'[openai]\n[openai.tenant]\nbase_url = "{BASE_URL}"\nmodel = "{MODEL}"\n'


async def test_no_tenant_gives_a_generator_that_reports_unavailable_without_a_client(tmp_path: Path) -> None:
    install_openai_files(tmp_path)

    with patch(_CLIENT) as build, capture_logs() as logs:
        generator = get_text_generator()
        result = await generator.generate("transcript", instructions="x", max_output_tokens=10)

    build.assert_not_called()
    assert generator.is_available() is False
    assert (result.status, result.error_code) == (OperationStatus.PERMANENT_ERROR, ErrorCode.TEXT_GENERATION_UNAVAILABLE)
    assert [entry["event"] for entry in logs] == ["text_generation_unconfigured"]
    assert "sk-" not in repr(logs)


def test_a_tenant_gives_the_openai_generator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_openai_files(tmp_path, base=_TENANT)
    monkeypatch.setenv("OPENAI__API_KEY", "sk-test-key")

    generator = get_text_generator()

    assert isinstance(generator, OpenAITextGenerator)
    assert generator.is_available() is True


def test_the_generator_is_resolved_once_per_process(tmp_path: Path) -> None:
    """Consumers ask on every modal; the configuration is read once."""
    install_openai_files(tmp_path)

    assert get_text_generator() is get_text_generator()
    assert get_text_generator_singleton.cache_info().misses == 1
