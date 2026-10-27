"""Unit tests for the OpenAI tenant entry's boot rules.

Each test installs files from tmp_path with every OpenAI variable removed (the autouse
isolation fixture) and builds the slice directly. OpenAI is never half configured: a tenant
entry needs the key and the key needs a tenant entry, an empty key counts as unset, and an
entry names both its endpoint and model. Each failure names the key at fault, and no failure
text carries the key's value.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError
from integrations.openai.settings import OpenAISettings
from tests.unit.integrations.openai.conftest import BASE_URL, MODEL, install_openai_files

pytestmark = pytest.mark.unit

_TENANT = f'[openai.tenant]\nbase_url = "{BASE_URL}"\nmodel = "{MODEL}"\n'


def test_a_tenant_without_the_key_fails_naming_the_key(tmp_path: Path) -> None:
    install_openai_files(tmp_path, environment=_TENANT)

    with pytest.raises(ConfigurationError, match="OPENAI__API_KEY"):
        OpenAISettings()


def test_an_empty_key_counts_as_unset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_openai_files(tmp_path, environment=_TENANT)
    monkeypatch.setenv("OPENAI__API_KEY", "")

    with pytest.raises(ConfigurationError, match="OPENAI__API_KEY"):
        OpenAISettings()


def test_the_key_without_a_tenant_fails_without_echoing_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_openai_files(tmp_path)
    monkeypatch.setenv("OPENAI__API_KEY", "sk-validate-0001")

    with pytest.raises(ConfigurationError, match=r"\[openai.tenant\]") as raised:
        OpenAISettings()

    assert "sk-validate-0001" not in str(raised.value)


@pytest.mark.parametrize("missing", ["base_url", "model"])
def test_a_tenant_missing_a_field_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    values = {"base_url": BASE_URL, "model": MODEL}
    del values[missing]
    install_openai_files(tmp_path, environment="[openai.tenant]\n" + "".join(f'{k} = "{v}"\n' for k, v in values.items()))
    monkeypatch.setenv("OPENAI__API_KEY", "sk-validate-0002")

    with pytest.raises(ConfigurationError, match=missing):
        OpenAISettings()


@pytest.mark.parametrize("base_url", ["http://models.example.test", "models.example.test", ""])
def test_a_base_url_off_https_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, base_url: str) -> None:
    install_openai_files(tmp_path, environment=f'[openai.tenant]\nbase_url = "{base_url}"\nmodel = "{MODEL}"\n')
    monkeypatch.setenv("OPENAI__API_KEY", "sk-validate-0003")

    with pytest.raises(ConfigurationError, match="base_url"):
        OpenAISettings()


def test_a_loopback_http_base_url_is_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A local model server on the developer's machine is reached over plain http."""
    install_openai_files(tmp_path, environment=f'[openai.tenant]\nbase_url = "http://localhost:11434/v1"\nmodel = "{MODEL}"\n')
    monkeypatch.setenv("OPENAI__API_KEY", "sk-validate-0004")

    assert OpenAISettings().base_url == "http://localhost:11434/v1"


@pytest.mark.parametrize(
    ("files", "key"),
    [
        ("[openai]\nmax_output_token = 10\n", "max_output_token"),
        (f'[openai.tenant]\nbase_url = "{BASE_URL}"\nmodel = "{MODEL}"\norganisation = "x"\n', "organisation"),
    ],
)
def test_an_unknown_key_fails_naming_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: str, key: str) -> None:
    install_openai_files(tmp_path, environment=files)
    monkeypatch.setenv("OPENAI__API_KEY", "sk-validate-0005")

    with pytest.raises(ConfigurationError, match=key):
        OpenAISettings()
