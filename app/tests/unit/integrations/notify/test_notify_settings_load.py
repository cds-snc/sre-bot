"""Unit tests for loading the GC Notify vendor slice from the [notify] table.

Each test installs a base and a local file from tmp_path (``install_notify_files``) with
every Notify variable removed and the .env file disabled (the autouse isolation fixture),
so it observes only the values it writes and sets. The timeout comes from [notify], the API
host from the optional [notify.tenant] entry, and the credentials only from
NOTIFY__SRE_USER_NAME and NOTIFY__SRE_CLIENT_SECRET.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationSlice
from integrations.notify.settings import NotifySettings, get_notify_settings
from tests.unit.integrations.notify.conftest import API_URL, TENANT, install_notify_files

pytestmark = pytest.mark.unit


def test_notify_settings_is_a_slice_on_the_notify_table() -> None:
    """The slice reads [notify] with the NOTIFY__ prefix and rejects unknown keys."""
    config = NotifySettings.model_config

    assert issubclass(NotifySettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("notify",)
    assert config.get("env_prefix") == "NOTIFY__"
    assert config.get("extra") == "forbid"


@pytest.mark.parametrize("field", list(NotifySettings.model_fields))
def test_notify_settings_fields_have_no_alias(field: str) -> None:
    """Every field is read only under its NOTIFY__<FIELD> name or file key: no alias widens it."""
    info = NotifySettings.model_fields[field]

    assert (info.alias, info.validation_alias) == (None, None)


def test_the_timeout_comes_from_the_notify_table(tmp_path: Path) -> None:
    install_notify_files(tmp_path, base="[notify]\ntimeout_seconds = 12.5\n")

    assert NotifySettings().timeout_seconds == 12.5


def test_nothing_set_is_notify_not_configured(tmp_path: Path) -> None:
    """With no entry and no credentials the slice loads with no tenant, which is not an error."""
    install_notify_files(tmp_path)

    settings = NotifySettings()

    assert settings.tenant is None
    assert settings.sre_user_name.get_secret_value() == ""
    assert settings.sre_client_secret.get_secret_value() == ""
    assert settings.timeout_seconds == 60.0


def test_the_tenant_entry_and_the_credentials_configure_notify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """[notify.tenant] names the API host; the credentials come from the environment."""
    install_notify_files(tmp_path, environment=TENANT)
    monkeypatch.setenv("NOTIFY__SRE_USER_NAME", "notify-user-0001")
    monkeypatch.setenv("NOTIFY__SRE_CLIENT_SECRET", "notify-secret-0001")

    settings = NotifySettings()

    assert settings.tenant is not None
    assert settings.tenant.api_url == API_URL
    assert settings.sre_user_name.get_secret_value() == "notify-user-0001"
    assert settings.sre_client_secret.get_secret_value() == "notify-secret-0001"


def test_the_credentials_never_appear_in_repr_str_or_dump(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_notify_files(tmp_path, environment=TENANT)
    monkeypatch.setenv("NOTIFY__SRE_USER_NAME", "notify-user-render")
    monkeypatch.setenv("NOTIFY__SRE_CLIENT_SECRET", "notify-secret-render")

    settings = NotifySettings()

    for rendered in (repr(settings), str(settings), repr(settings.model_dump())):
        assert "notify-user-render" not in rendered
        assert "notify-secret-render" not in rendered


def test_get_notify_settings_is_cached(tmp_path: Path) -> None:
    install_notify_files(tmp_path)

    assert get_notify_settings() is get_notify_settings()
