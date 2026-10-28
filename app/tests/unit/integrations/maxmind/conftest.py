"""Isolation fixtures for MaxMind integration unit tests.

``_maxmind_env_isolation`` (autouse) removes every MAXMIND_* and MAXMIND__* variable, disables the
.env file and clears the cached providers, so a test observes only the files it installs and the
variables it sets. ``install_maxmind_files`` writes a base and a local file into tmp_path and
installs them.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import install_configuration_files
from integrations.maxmind.client import get_maxmind_client
from integrations.maxmind.settings import MaxMindSettings, get_maxmind_settings
from server.configuration.loader import TomlConfigurationFiles

RETIRED_NAMES = ("MAXMIND_DB_PATH", "MAXMIND_KEY")
DATABASE_PATH = "./geodb/test-City.mmdb"
TENANT = f'[maxmind.tenant]\ndatabase_path = "{DATABASE_PATH}"\n'


@pytest.fixture(autouse=True)
def _maxmind_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply env + cache isolation for every MaxMind unit test."""
    monkeypatch.setitem(MaxMindSettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.startswith("MAXMIND_"):
            monkeypatch.delenv(key, raising=False)
    get_maxmind_settings.cache_clear()
    get_maxmind_client.cache_clear()
    yield
    get_maxmind_settings.cache_clear()
    get_maxmind_client.cache_clear()


def install_maxmind_files(tmp_path: Path, base: str = "[maxmind]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )
