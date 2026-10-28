"""Isolation fixtures for Trello integration unit tests.

``_trello_env_isolation`` (autouse) removes every TRELLO_* and TRELLO__* variable, disables the
.env file and clears the cached provider, so a test observes only the files it installs and the
variables it sets. ``install_trello_files`` writes a base and a local file into tmp_path and
installs them.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import install_configuration_files
from integrations.trello.settings import TrelloSettings, get_trello_settings
from server.configuration.loader import TomlConfigurationFiles

RETIRED_NAMES = ("TRELLO_APP_KEY", "TRELLO_TOKEN", "TRELLO_ATIP_BOARD", "TRELLO__APP_KEY", "TRELLO__TOKEN")


@pytest.fixture(autouse=True)
def _trello_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply env + cache isolation for every Trello unit test."""
    monkeypatch.setitem(TrelloSettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.startswith("TRELLO_"):
            monkeypatch.delenv(key, raising=False)
    get_trello_settings.cache_clear()
    yield
    get_trello_settings.cache_clear()


def install_trello_files(tmp_path: Path, base: str = "[trello]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )
