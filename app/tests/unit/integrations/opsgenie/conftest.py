"""Isolation fixtures for Opsgenie integration unit tests.

``_opsgenie_env_isolation`` (autouse) removes every OPSGENIE_* and OPSGENIE__* variable, disables
the .env file and clears the cached provider, so a test observes only the files it installs and
the variables it sets. ``install_opsgenie_files`` writes a base and a local file into tmp_path and
installs them.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import install_configuration_files
from integrations.opsgenie.settings import OpsGenieSettings, get_opsgenie_settings
from server.configuration.loader import TomlConfigurationFiles

RETIRED_NAMES = ("OPSGENIE_INTEGRATIONS_KEY", "OPSGENIE_KEY")
API_URL = "https://api.opsgenie.example.test"
TENANT = f'[opsgenie.tenant]\napi_url = "{API_URL}"\n'


@pytest.fixture(autouse=True)
def _opsgenie_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply env + cache isolation for every Opsgenie unit test."""
    monkeypatch.setitem(OpsGenieSettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.startswith("OPSGENIE_"):
            monkeypatch.delenv(key, raising=False)
    get_opsgenie_settings.cache_clear()
    yield
    get_opsgenie_settings.cache_clear()


def install_opsgenie_files(tmp_path: Path, base: str = "[opsgenie]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )
