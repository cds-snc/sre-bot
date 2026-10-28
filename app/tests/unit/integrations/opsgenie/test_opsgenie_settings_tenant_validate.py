"""Unit tests for the Opsgenie tenant entry's boot rules.

Each test installs files from tmp_path with every Opsgenie variable removed (the autouse
isolation fixture) and builds the slice directly. Opsgenie is never half configured: an entry
needs the key and the key needs an entry, an empty key counts as unset, and the regional API
host is https. Each failure names the key at fault, and no failure text carries the key.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError
from integrations.opsgenie.settings import OpsGenieSettings
from tests.unit.integrations.opsgenie.conftest import TENANT, install_opsgenie_files

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("key", [None, ""])
def test_a_tenant_without_the_key_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str | None) -> None:
    install_opsgenie_files(tmp_path, environment=TENANT)
    if key is not None:
        monkeypatch.setenv("OPSGENIE__INTEGRATIONS_KEY", key)

    with pytest.raises(ConfigurationError, match="OPSGENIE__INTEGRATIONS_KEY"):
        OpsGenieSettings()


def test_the_key_without_a_tenant_fails_without_echoing_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_opsgenie_files(tmp_path)
    monkeypatch.setenv("OPSGENIE__INTEGRATIONS_KEY", "genie-validate-0001")

    with pytest.raises(ConfigurationError, match=r"\[opsgenie.tenant\]") as raised:
        OpsGenieSettings()

    assert "genie-validate-0001" not in str(raised.value)


@pytest.mark.parametrize("api_url", ["http://api.opsgenie.com", "api.opsgenie.com", ""])
def test_an_api_url_off_https_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, api_url: str) -> None:
    install_opsgenie_files(tmp_path, environment=f'[opsgenie.tenant]\napi_url = "{api_url}"\n')
    monkeypatch.setenv("OPSGENIE__INTEGRATIONS_KEY", "genie-validate-0002")

    with pytest.raises(ConfigurationError, match="api_url"):
        OpsGenieSettings()


@pytest.mark.parametrize(
    ("files", "key"),
    [
        ("[opsgenie]\ntimeout = 10\n", "timeout"),
        (TENANT + 'region = "eu"\n', "region"),
    ],
)
def test_an_unknown_key_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: str, key: str) -> None:
    install_opsgenie_files(tmp_path, environment=files)
    monkeypatch.setenv("OPSGENIE__INTEGRATIONS_KEY", "genie-validate-0003")

    with pytest.raises(ConfigurationError, match=key):
        OpsGenieSettings()
