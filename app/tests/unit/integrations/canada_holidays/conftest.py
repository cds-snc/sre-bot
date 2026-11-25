"""Isolation fixtures for Canada Holidays integration unit tests.

``_canada_holidays_env_isolation`` (autouse) removes every CANADA_HOLIDAYS_* variable, disables
the .env file and clears the cached provider, so a test observes only the files it installs and
the variables it sets. ``install_canada_holidays_files`` writes a base and a local file into
tmp_path and installs them.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import install_configuration_files
from integrations.canada_holidays.settings import CanadaHolidaysSettings, get_canada_holidays_settings
from server.configuration.loader import TomlConfigurationFiles

BASE_URL = "https://holidays.example.test/api/v1"
TENANT = f'[canada_holidays.tenant]\nbase_url = "{BASE_URL}"\n'


@pytest.fixture(autouse=True)
def _canada_holidays_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply env + cache isolation for every Canada Holidays unit test."""
    monkeypatch.setitem(CanadaHolidaysSettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.startswith("CANADA_HOLIDAYS_"):
            monkeypatch.delenv(key, raising=False)
    get_canada_holidays_settings.cache_clear()
    yield
    get_canada_holidays_settings.cache_clear()


def install_canada_holidays_files(tmp_path: Path, base: str = "[canada_holidays]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )
