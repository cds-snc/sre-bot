"""Behavior tests for the instance languages slice on the [languages] table.

Settings are built under the installed configuration files, with the slice's
variable removed so each test controls the environment. A list from the
environment is JSON, as pydantic-settings reads complex fields. Invalid lists
fail at construction with a ConfigurationError naming the table and key, which
the configuration phase turns into a boot failure.
"""

import json

import pytest

from contracts.configuration import ConfigurationError
from server.languages.settings import LanguageSettings, get_language_settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the slice's variable and clear the provider cache around each test."""
    monkeypatch.delenv("LANGUAGES__SHARED", raising=False)
    get_language_settings.cache_clear()
    yield
    get_language_settings.cache_clear()


def test_the_default_is_english_then_french() -> None:
    """The base file keeps today's order, so merging changes no notice."""
    assert get_language_settings().shared == ("en-US", "fr-FR")


@pytest.mark.parametrize("raw", ['["fr-FR", "en-US"]', '["en-US"]', '["fr-FR"]'])
def test_an_instance_sets_its_own_languages_and_order(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("LANGUAGES__SHARED", raw)

    assert list(LanguageSettings().shared) == json.loads(raw)


@pytest.mark.parametrize(
    ("shared", "reason"),
    [
        ([], "at least one language"),
        (["en-US", "en-US"], "more than once"),
        (["es-ES"], "not supported"),
    ],
)
def test_an_invalid_list_fails_at_construction(shared: list[str], reason: str) -> None:
    with pytest.raises(ConfigurationError, match=reason):
        LanguageSettings(shared=shared)
