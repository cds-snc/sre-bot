"""Tests for the OpenAI tables in the checked-in configuration files.

Each environment's files are read with the real loader and the OpenAI slice is built on them,
with OPENAI__API_KEY set where the environment names a tenant (the key is a secret, never in a
file) and blanked otherwise. production.toml and local.toml name the deployment's model endpoint;
base.toml and ci.toml configure no tenant, so the test run has OpenAI not configured. The raw
files are also searched for a key under the OpenAI tables.
"""

import tomllib
from collections.abc import Iterator

import pytest

from contracts.configuration import install_configuration_files
from integrations.openai.settings import OpenAISettings
from server.configuration.loader import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Build the slice from the files only, never a developer's .env or Codespaces secrets."""
    monkeypatch.setitem(OpenAISettings.model_config, "env_file", None)
    monkeypatch.setenv("OPENAI__API_KEY", "")
    yield


@pytest.mark.parametrize("environment", ["production", "local"])
def test_deployed_environments_name_the_model_endpoint(environment: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The tenant entry validates with a key supplied from the environment."""
    install_configuration_files(load_configuration_files(environment))
    monkeypatch.setenv("OPENAI__API_KEY", "sk-files-0001")

    settings = OpenAISettings()

    assert settings.tenant is not None
    assert settings.base_url.startswith("https://")
    assert settings.model


def test_ci_configures_no_openai_tenant() -> None:
    """The test run has OpenAI not configured."""
    install_configuration_files(load_configuration_files("ci"))

    assert OpenAISettings().tenant is None


def test_base_names_no_tenant_and_only_the_tuning() -> None:
    """The base file holds the framework's tuning, never the deploying organisation's endpoint."""
    table = tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))["openai"]

    assert set(table) == {"max_output_tokens", "temperature", "timeout_seconds"}


@pytest.mark.parametrize("name", ["base.toml", "local.toml", "ci.toml", "production.toml"])
def test_no_file_holds_an_openai_key(name: str) -> None:
    """The key comes only from OPENAI__API_KEY."""
    table = tomllib.loads((CONFIG_DIR / name).read_text(encoding="utf-8")).get("openai", {})

    assert "api_key" not in table
    assert "api_key" not in table.get("tenant", {})
    assert "sk-" not in repr(table)
