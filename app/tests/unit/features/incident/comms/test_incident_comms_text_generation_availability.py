"""Tests for the predicate that says whether AI drafting is offered.

The adapter's ``get_openai_settings`` is patched with a stand-in slice, once with a tenant
entry and once without (OpenAI not configured), and ``get_summarizer`` with a stand-in, so no
network client is ever constructed. The provider cache is cleared around each test, so each
case builds the generator from its own patch.
"""

from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from features.incident.comms import providers
from features.incident.comms.service import text_generation_available

pytestmark = pytest.mark.unit

_MODULE = "features.incident.comms.adapters.text_generation"


def _openai(*, configured: bool) -> SimpleNamespace:
    return SimpleNamespace(tenant=object() if configured else None)


@pytest.fixture(autouse=True)
def _clear_generator_cache() -> Iterator[None]:
    """The generator is cached per process; each case builds its own."""
    providers.get_status_update_text_generator.cache_clear()
    yield
    providers.get_status_update_text_generator.cache_clear()


def test_ai_is_available_when_openai_is_configured() -> None:
    """A tenant entry means the form may offer AI drafting."""
    with (
        patch(f"{_MODULE}.get_openai_settings", return_value=_openai(configured=True)),
        patch(f"{_MODULE}.get_summarizer", return_value=MagicMock()),
    ):
        assert text_generation_available() is True


def test_ai_is_unavailable_when_openai_is_not_configured() -> None:
    """Without a tenant entry the form offers writing by hand only."""
    with patch(f"{_MODULE}.get_openai_settings", return_value=_openai(configured=False)):
        assert text_generation_available() is False


def test_the_answer_is_stable_for_the_process() -> None:
    """The generator is built once, so the predicate does not re-read settings on every modal."""
    with (
        patch(f"{_MODULE}.get_openai_settings", return_value=_openai(configured=True)),
        patch(f"{_MODULE}.get_summarizer", return_value=MagicMock()) as get_summarizer,
    ):
        text_generation_available()
        text_generation_available()

    get_summarizer.assert_called_once_with()
