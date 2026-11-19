"""Isolation fixtures for the text-generation capability's unit tests.

``_isolation`` (autouse) removes every OPENAI_* and OPENAI__* variable, disables the .env file
and clears the cached OpenAI slice and the capability's cached generator, so a test observes only
the files it installs and the variables it sets. ``install_openai_files`` writes a base and a
local file into tmp_path and installs them; ``openai_settings`` is a configured slice.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from capabilities.text_generation.providers import get_text_generator_singleton
from contracts.configuration import install_configuration_files
from integrations.openai.settings import OpenAISettings, OpenAITenant, get_openai_settings
from server.configuration.loader import TomlConfigurationFiles

BASE_URL = "https://models.example.test"
MODEL = "test-model"


@pytest.fixture(autouse=True)
def _isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(OpenAISettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.startswith("OPENAI_"):
            monkeypatch.delenv(key, raising=False)
    get_openai_settings.cache_clear()
    get_text_generator_singleton.cache_clear()
    yield
    get_openai_settings.cache_clear()
    get_text_generator_singleton.cache_clear()


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
    return OpenAISettings(tenant=OpenAITenant(base_url=BASE_URL, model=MODEL), api_key="sk-test-key")
