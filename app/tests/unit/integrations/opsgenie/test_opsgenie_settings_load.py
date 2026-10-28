"""Unit tests for loading the Opsgenie vendor slice from the [opsgenie] table.

Each test installs a base and a local file from tmp_path (``install_opsgenie_files``) with
every Opsgenie variable removed and the .env file disabled (the autouse isolation fixture),
so it observes only the values it writes and sets. The timeout comes from [opsgenie], the
regional API host from the optional [opsgenie.tenant] entry, and the key only from
OPSGENIE__INTEGRATIONS_KEY. The retired flat names are ignored in the environment and in a
.env file.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationSlice
from integrations.opsgenie.settings import OpsGenieSettings, get_opsgenie_settings
from tests.unit.integrations.opsgenie.conftest import API_URL, RETIRED_NAMES, TENANT, install_opsgenie_files

pytestmark = pytest.mark.unit


def test_opsgenie_settings_is_a_slice_on_the_opsgenie_table() -> None:
    """The slice reads [opsgenie] with the OPSGENIE__ prefix and rejects unknown keys."""
    config = OpsGenieSettings.model_config

    assert issubclass(OpsGenieSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("opsgenie",)
    assert config.get("env_prefix") == "OPSGENIE__"
    assert config.get("extra") == "forbid"


@pytest.mark.parametrize("field", list(OpsGenieSettings.model_fields))
def test_opsgenie_settings_fields_have_no_alias(field: str) -> None:
    """Every field is read only under its OPSGENIE__<FIELD> name or file key: no alias widens it."""
    info = OpsGenieSettings.model_fields[field]

    assert (info.alias, info.validation_alias) == (None, None)


def test_the_timeout_comes_from_the_opsgenie_table(tmp_path: Path) -> None:
    install_opsgenie_files(tmp_path, base="[opsgenie]\ntimeout_seconds = 7.5\n")

    assert OpsGenieSettings().timeout_seconds == 7.5


def test_nothing_set_is_opsgenie_not_configured(tmp_path: Path) -> None:
    install_opsgenie_files(tmp_path)

    settings = OpsGenieSettings()

    assert settings.tenant is None
    assert settings.integrations_key.get_secret_value() == ""
    assert settings.timeout_seconds == 30.0


def test_the_tenant_entry_and_the_key_configure_opsgenie(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_opsgenie_files(tmp_path, environment=TENANT)
    monkeypatch.setenv("OPSGENIE__INTEGRATIONS_KEY", "genie-load-0001")

    settings = OpsGenieSettings()

    assert settings.tenant is not None
    assert settings.tenant.api_url == API_URL
    assert settings.integrations_key.get_secret_value() == "genie-load-0001"


def test_the_key_never_appears_in_repr_str_or_dump(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_opsgenie_files(tmp_path, environment=TENANT)
    monkeypatch.setenv("OPSGENIE__INTEGRATIONS_KEY", "genie-render-0001")

    settings = OpsGenieSettings()

    for rendered in (repr(settings), str(settings), repr(settings.model_dump())):
        assert "genie-render-0001" not in rendered


def test_the_retired_names_are_ignored_in_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_opsgenie_files(tmp_path)
    for name in RETIRED_NAMES:
        monkeypatch.setenv(name, "retired")

    assert OpsGenieSettings().integrations_key.get_secret_value() == ""


def test_the_retired_names_are_ignored_in_a_dotenv_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_opsgenie_files(tmp_path)
    dotenv = tmp_path / ".env"
    dotenv.write_text("\n".join(f"{name}=retired" for name in RETIRED_NAMES) + "\n", encoding="utf-8")
    monkeypatch.setitem(OpsGenieSettings.model_config, "env_file", str(dotenv))

    assert OpsGenieSettings().integrations_key.get_secret_value() == ""


def test_get_opsgenie_settings_is_cached(tmp_path: Path) -> None:
    install_opsgenie_files(tmp_path)

    assert get_opsgenie_settings() is get_opsgenie_settings()
