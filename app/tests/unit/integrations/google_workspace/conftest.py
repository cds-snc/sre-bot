"""Shared fixtures for the Google Workspace slice tests.

``google_slice_env`` removes the slice's GOOGLE_WORKSPACE__ variables, disables the
.env file and clears the cached provider, so a test observes only the files it installs and the
variables it sets. ``install_google_files`` writes a base and a local file into
tmp_path and installs them.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import install_configuration_files
from integrations.google_workspace.settings import GoogleWorkspaceSettings, get_google_workspace_settings
from server.configuration.loader import TomlConfigurationFiles

TENANT_NAMES = (
    "GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID",
    "GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY",
    "GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL",
)


@pytest.fixture
def google_slice_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in TENANT_NAMES:
        monkeypatch.delenv(name, raising=False)
    for field in GoogleWorkspaceSettings.model_fields:
        monkeypatch.delenv(f"GOOGLE_WORKSPACE__{field.upper()}", raising=False)
    monkeypatch.setitem(GoogleWorkspaceSettings.model_config, "env_file", None)
    get_google_workspace_settings.cache_clear()
    yield
    get_google_workspace_settings.cache_clear()


def install_google_files(tmp_path: Path, base: str = "[google_workspace]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )
