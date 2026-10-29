"""Unit tests for the access-owned permission-set slice, the [access_permission_sets] table.

Each test installs a base and a local file from tmp_path with the .env file disabled.
The two values are the permission-set ARNs the 'write' and 'read' aliases resolve to.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, ConfigurationSlice, install_configuration_files
from packages.access.common.settings import AccessPermissionSetsSettings, get_access_permission_sets_settings
from server.configuration.loader import TomlConfigurationFiles

pytestmark = pytest.mark.unit

ADMIN = "arn:aws:sso:::permissionSet/ssoins-1234567890abcdef/ps-admin"
VIEW = "arn:aws:sso:::permissionSet/ssoins-1234567890abcdef/ps-viewer"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(AccessPermissionSetsSettings.model_config, "env_file", None)
    for name in (
        "ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS",
        "ACCESS_PERMISSION_SETS__VIEW_ONLY_PERMISSIONS",
    ):
        monkeypatch.delenv(name, raising=False)
    get_access_permission_sets_settings.cache_clear()
    yield
    get_access_permission_sets_settings.cache_clear()


def _install(tmp_path: Path, base: str, environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )


def test_permission_sets_settings_is_a_slice_on_its_own_table() -> None:
    """The slice reads [access_permission_sets] with the ACCESS_PERMISSION_SETS__ prefix and rejects unknown keys."""
    config = AccessPermissionSetsSettings.model_config

    assert issubclass(AccessPermissionSetsSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("access_permission_sets",)
    assert config.get("env_prefix") == "ACCESS_PERMISSION_SETS__"
    assert config.get("extra") == "forbid"


def test_permission_sets_default_to_empty(tmp_path: Path) -> None:
    """The base file's empty values leave both aliases unresolved until an environment names them."""
    _install(tmp_path, "[access_permission_sets]\n")

    settings = AccessPermissionSetsSettings()

    assert (settings.system_admin_permissions, settings.view_only_permissions) == ("", "")


def test_permission_sets_read_the_environment_file(tmp_path: Path) -> None:
    """The environment file's values override the base file's, key by key."""
    _install(
        tmp_path,
        '[access_permission_sets]\nsystem_admin_permissions = ""\nview_only_permissions = ""\n',
        f'[access_permission_sets]\nsystem_admin_permissions = "{ADMIN}"\nview_only_permissions = "{VIEW}"\n',
    )

    settings = get_access_permission_sets_settings()

    assert (settings.system_admin_permissions, settings.view_only_permissions) == (ADMIN, VIEW)


def test_permission_sets_unknown_key_fails_naming_the_key(tmp_path: Path) -> None:
    """A misspelt key stops the build naming the key."""
    _install(tmp_path, "[access_permission_sets]\nsystem_admin_permission = 'x'\n")

    with pytest.raises(ConfigurationError, match="system_admin_permission"):
        AccessPermissionSetsSettings()
