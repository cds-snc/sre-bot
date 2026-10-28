"""Isolation fixtures for GC Notify integration unit tests.

``_notify_env_isolation`` (autouse) removes every NOTIFY_* and NOTIFY__* variable, disables the
.env file and clears the cached provider, so a test observes only the files it installs and the
variables it sets. ``install_notify_files`` writes a base and a local file into tmp_path and
installs them.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import install_configuration_files
from integrations.notify.settings import NotifySettings, get_notify_settings
from server.configuration.loader import TomlConfigurationFiles

RETIRED_NAMES = ("NOTIFY_SRE_USER_NAME", "NOTIFY_SRE_CLIENT_SECRET", "NOTIFY_API_URL")
API_URL = "https://notify.example.test"
TENANT = f'[notify.tenant]\napi_url = "{API_URL}"\n'


@pytest.fixture(autouse=True)
def _notify_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply env + cache isolation for every Notify unit test."""
    monkeypatch.setitem(NotifySettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.startswith("NOTIFY_"):
            monkeypatch.delenv(key, raising=False)
    get_notify_settings.cache_clear()
    yield
    get_notify_settings.cache_clear()


def install_notify_files(tmp_path: Path, base: str = "[notify]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )
