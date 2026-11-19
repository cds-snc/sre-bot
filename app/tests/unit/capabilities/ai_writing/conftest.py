"""Isolation fixtures for the AI writing capability's unit tests.

``_isolation`` (autouse) removes every OPENAI_* and AI_WRITING_* variable, disables the .env
files and clears the cached OpenAI and [ai_writing] slices and the capability's cached writer, so
a test observes only the files it installs and the variables it sets. ``install_openai_files``
writes a base and a local file into tmp_path and installs them; ``openai_settings`` is a
configured vendor slice.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from capabilities.ai_writing.providers import get_ai_writer_singleton
from capabilities.ai_writing.settings import AIWritingSettings, get_ai_writing_settings
from contracts.configuration import install_configuration_files
from integrations.openai.settings import OpenAISettings, OpenAITenant, get_openai_settings
from server.configuration.loader import TomlConfigurationFiles

BASE_URL = "https://models.example.test"
MODEL = "test-model"


@pytest.fixture(autouse=True)
def _isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(OpenAISettings.model_config, "env_file", None)
    monkeypatch.setitem(AIWritingSettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.startswith(("OPENAI_", "AI_WRITING_")):
            monkeypatch.delenv(key, raising=False)
    _clear_caches()
    yield
    _clear_caches()


def _clear_caches() -> None:
    get_openai_settings.cache_clear()
    get_ai_writing_settings.cache_clear()
    get_ai_writer_singleton.cache_clear()


def install_openai_files(tmp_path: Path, base: str = "[openai]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )


@pytest.fixture
def openai_settings(tmp_path: Path) -> OpenAISettings:
    """A configured ``OpenAISettings``: a tenant entry and a dummy API key."""
    install_openai_files(tmp_path)
    return OpenAISettings(tenant=OpenAITenant(base_url=BASE_URL), api_key="sk-test-key")
