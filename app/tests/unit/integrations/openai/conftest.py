"""Isolation fixtures for OpenAI integration unit tests.

Clears cached settings and OPENAI_* environment variables between tests so
that each test observes a clean configuration surface.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from integrations.openai.settings import OpenAISettings, get_openai_settings


def _clear_openai_caches() -> None:
    """Reset the cached settings singleton."""
    get_openai_settings.cache_clear()


def _clear_openai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every OPENAI_* variable so tests cannot read host values."""
    for key in tuple(os.environ):
        if key.startswith("OPENAI_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _openai_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply env + cache isolation for every OpenAI unit test."""
    monkeypatch.setitem(OpenAISettings.model_config, "env_file", None)
    _clear_openai_env(monkeypatch)
    _clear_openai_caches()
    yield
    _clear_openai_caches()


@pytest.fixture
def openai_settings(monkeypatch: pytest.MonkeyPatch) -> OpenAISettings:
    """A valid ``OpenAISettings`` instance with a dummy API key."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    return OpenAISettings()
