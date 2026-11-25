"""Unit tests for loading the Canada Holidays vendor slice from the [canada_holidays] table.

Each test installs a base and a local file from tmp_path (``install_canada_holidays_files``) with
every Canada Holidays variable removed and the .env file disabled (the autouse isolation
fixture), so it observes only the values it writes. The transport tuning comes from
[canada_holidays] and the API host from the optional [canada_holidays.tenant] entry: the API is
open source and self-hostable, so the host is the deployment's choice. No credential exists.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, ConfigurationSlice
from integrations.canada_holidays.settings import CanadaHolidaysSettings, get_canada_holidays_settings
from tests.unit.integrations.canada_holidays.conftest import BASE_URL, TENANT, install_canada_holidays_files

pytestmark = pytest.mark.unit


def test_the_slice_reads_the_canada_holidays_table() -> None:
    config = CanadaHolidaysSettings.model_config

    assert issubclass(CanadaHolidaysSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("canada_holidays",)
    assert config.get("env_prefix") == "CANADA_HOLIDAYS__"
    assert config.get("extra") == "forbid"


@pytest.mark.parametrize("field", list(CanadaHolidaysSettings.model_fields))
def test_fields_have_no_alias(field: str) -> None:
    info = CanadaHolidaysSettings.model_fields[field]

    assert (info.alias, info.validation_alias) == (None, None)


def test_nothing_set_is_not_configured_with_the_default_tuning(tmp_path: Path) -> None:
    install_canada_holidays_files(tmp_path)

    settings = CanadaHolidaysSettings()

    assert settings.tenant is None
    assert settings.timeout_seconds == 10.0
    assert settings.connect_retries == 2


def test_the_tenant_entry_names_the_api_host(tmp_path: Path) -> None:
    install_canada_holidays_files(tmp_path, environment=TENANT)

    settings = CanadaHolidaysSettings()

    assert settings.tenant is not None
    assert settings.tenant.base_url == BASE_URL


def test_the_tuning_comes_from_the_table(tmp_path: Path) -> None:
    install_canada_holidays_files(tmp_path, base="[canada_holidays]\ntimeout_seconds = 4.5\nconnect_retries = 0\n")

    settings = CanadaHolidaysSettings()

    assert (settings.timeout_seconds, settings.connect_retries) == (4.5, 0)


@pytest.mark.parametrize(
    ("base", "match"),
    [
        ("[canada_holidays]\ntimeout_seconds = 0\n", "timeout_seconds"),
        ("[canada_holidays]\nconnect_retries = -1\n", "connect_retries"),
        ('[canada_holidays.tenant]\nbase_url = "http://holidays.example.test"\n', "https"),
        ("[canada_holidays]\nunknown = 1\n", "unknown"),
    ],
    ids=["zero_timeout", "negative_retries", "plain_http", "unknown_key"],
)
def test_invalid_values_fail_loading(tmp_path: Path, base: str, match: str) -> None:
    install_canada_holidays_files(tmp_path, base=base)

    with pytest.raises(ConfigurationError, match=match):
        CanadaHolidaysSettings()


def test_get_canada_holidays_settings_is_cached(tmp_path: Path) -> None:
    install_canada_holidays_files(tmp_path)

    assert get_canada_holidays_settings() is get_canada_holidays_settings()
