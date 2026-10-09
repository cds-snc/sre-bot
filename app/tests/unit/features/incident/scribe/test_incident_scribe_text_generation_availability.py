"""Tests for the predicate that says whether AI drafting is offered.

The adapter's ``get_summarizer`` is patched, once returning a stand-in
summarizer and once raising the pydantic ``ValidationError`` that loading the
OpenAI settings raises without an API key. The provider cache is cleared
around each test, so each case builds the generator from its own patch and no
network client is ever constructed.
"""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from features.incident.scribe import providers
from features.incident.scribe.status_update import text_generation_available

pytestmark = pytest.mark.unit

_TARGET = "features.incident.scribe.adapters.text_generation.get_summarizer"


class _RequiredKey(BaseModel):
    api_key: str


def _missing_key_error() -> ValidationError:
    try:
        _RequiredKey.model_validate({})
    except ValidationError as error:
        return error
    raise AssertionError("validation unexpectedly passed")


@pytest.fixture(autouse=True)
def _clear_generator_cache() -> Iterator[None]:
    """The generator is cached per process; each case builds its own."""
    providers.get_status_update_text_generator.cache_clear()
    yield
    providers.get_status_update_text_generator.cache_clear()


def test_ai_is_available_when_the_openai_settings_load() -> None:
    """A configured integration means the form may offer AI drafting."""
    with patch(_TARGET, return_value=MagicMock()):
        assert text_generation_available() is True


def test_ai_is_unavailable_when_the_openai_settings_do_not_load() -> None:
    """Without a key the form offers writing by hand only."""
    with patch(_TARGET, side_effect=_missing_key_error()):
        assert text_generation_available() is False


def test_the_answer_is_stable_for_the_process() -> None:
    """The generator is built once, so the predicate does not re-read settings on every modal."""
    with patch(_TARGET, return_value=MagicMock()) as get_summarizer:
        text_generation_available()
        text_generation_available()

    get_summarizer.assert_called_once_with()
