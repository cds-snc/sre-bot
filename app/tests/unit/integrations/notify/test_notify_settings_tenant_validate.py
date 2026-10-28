"""Unit tests for the GC Notify tenant entry's boot rules.

Each test installs files from tmp_path with every Notify variable removed (the autouse
isolation fixture) and builds the slice directly. Notify is never half configured: an entry
needs both credentials, either credential needs an entry, an empty credential counts as
unset, and the API host is https. Each failure names the key at fault, and no failure text
carries a credential.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError
from integrations.notify.settings import NotifySettings
from tests.unit.integrations.notify.conftest import TENANT, install_notify_files

pytestmark = pytest.mark.unit

_CREDENTIALS = ("NOTIFY__SRE_USER_NAME", "NOTIFY__SRE_CLIENT_SECRET")


@pytest.mark.parametrize("missing", _CREDENTIALS)
def test_a_tenant_without_a_credential_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    install_notify_files(tmp_path, environment=TENANT)
    for name in _CREDENTIALS:
        monkeypatch.setenv(name, "" if name == missing else "notify-validate-0001")

    with pytest.raises(ConfigurationError, match=missing) as raised:
        NotifySettings()

    assert "notify-validate-0001" not in str(raised.value)


@pytest.mark.parametrize("present", _CREDENTIALS)
def test_a_credential_without_a_tenant_fails_without_echoing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, present: str
) -> None:
    install_notify_files(tmp_path)
    monkeypatch.setenv(present, "notify-validate-0002")

    with pytest.raises(ConfigurationError, match=r"\[notify.tenant\]") as raised:
        NotifySettings()

    assert present in str(raised.value)
    assert "notify-validate-0002" not in str(raised.value)


@pytest.mark.parametrize("api_url", ["http://notify.example.test", "notify.example.test", ""])
def test_an_api_url_off_https_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, api_url: str) -> None:
    install_notify_files(tmp_path, environment=f'[notify.tenant]\napi_url = "{api_url}"\n')
    for name in _CREDENTIALS:
        monkeypatch.setenv(name, "notify-validate-0003")

    with pytest.raises(ConfigurationError, match="api_url"):
        NotifySettings()


@pytest.mark.parametrize(
    ("files", "key"),
    [
        ("[notify]\ntimeout_second = 10\n", "timeout_second"),
        (TENANT + 'service_id = "x"\n', "service_id"),
    ],
)
def test_an_unknown_key_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: str, key: str) -> None:
    install_notify_files(tmp_path, environment=files)
    for name in _CREDENTIALS:
        monkeypatch.setenv(name, "notify-validate-0004")

    with pytest.raises(ConfigurationError, match=key):
        NotifySettings()
