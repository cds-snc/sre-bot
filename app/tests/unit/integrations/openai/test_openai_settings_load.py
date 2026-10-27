"""Unit tests for loading the OpenAI vendor slice from the [openai] table.

Each test installs a base and a local file from tmp_path (``install_openai_files``) with
every OpenAI variable removed and the .env file disabled (the autouse isolation fixture),
so it observes only the values it writes and sets. The tuning comes from [openai], the
model endpoint from the optional [openai.tenant] entry, and the key only from
OPENAI__API_KEY. The six retired OPENAI_* names are ignored in the environment and in a
.env file.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationSlice
from integrations.openai.settings import OpenAISettings, get_openai_settings
from tests.unit.integrations.openai.conftest import BASE_URL, MODEL, RETIRED_NAMES, install_openai_files

pytestmark = pytest.mark.unit

_TENANT = f'[openai.tenant]\nbase_url = "{BASE_URL}"\nmodel = "{MODEL}"\n'


def test_openai_settings_is_a_slice_on_the_openai_table() -> None:
    """The slice reads [openai] with the OPENAI__ prefix and rejects unknown keys."""
    config = OpenAISettings.model_config

    assert issubclass(OpenAISettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("openai",)
    assert config.get("env_prefix") == "OPENAI__"
    assert config.get("extra") == "forbid"


@pytest.mark.parametrize("field", list(OpenAISettings.model_fields))
def test_openai_settings_fields_have_no_alias(field: str) -> None:
    """Every field is read only under its OPENAI__<FIELD> name or file key: no alias widens it."""
    info = OpenAISettings.model_fields[field]

    assert (info.alias, info.validation_alias) == (None, None)


def test_tuning_comes_from_the_openai_table(tmp_path: Path) -> None:
    """[openai] sets the completion budget, temperature and timeout."""
    install_openai_files(tmp_path, base="[openai]\nmax_output_tokens = 1234\ntemperature = 0.25\ntimeout_seconds = 42.5\n")

    settings = OpenAISettings()

    assert (settings.max_output_tokens, settings.temperature, settings.timeout_seconds) == (1234, 0.25, 42.5)


def test_no_tenant_and_no_key_is_openai_not_configured(tmp_path: Path) -> None:
    """With neither, the slice loads with no tenant: OpenAI is not configured, which is not an error."""
    install_openai_files(tmp_path)

    settings = OpenAISettings()

    assert settings.tenant is None
    assert settings.api_key.get_secret_value() == ""


def test_the_tenant_entry_and_the_key_configure_openai(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """[openai.tenant] names the endpoint and model; OPENAI__API_KEY supplies the key."""
    install_openai_files(tmp_path, environment=_TENANT)
    monkeypatch.setenv("OPENAI__API_KEY", "sk-load-0001")

    settings = OpenAISettings()

    assert settings.tenant is not None
    assert (settings.base_url, settings.model) == (BASE_URL, MODEL)
    assert settings.api_key.get_secret_value() == "sk-load-0001"


def test_the_key_never_appears_in_repr_str_or_dump(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The secret is masked wherever the slice is rendered."""
    install_openai_files(tmp_path, environment=_TENANT)
    monkeypatch.setenv("OPENAI__API_KEY", "sk-render-0001")

    settings = OpenAISettings()

    assert "sk-render-0001" not in repr(settings)
    assert "sk-render-0001" not in str(settings)
    assert "sk-render-0001" not in repr(settings.model_dump())


def test_the_retired_names_are_ignored_in_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """None of the six OPENAI_* names configures the slice from the environment."""
    install_openai_files(tmp_path)
    for name in RETIRED_NAMES:
        monkeypatch.setenv(name, "https://retired.example.test" if name == "OPENAI_BASE_URL" else "7")

    settings = OpenAISettings()

    assert settings.tenant is None
    assert settings.api_key.get_secret_value() == ""
    assert (settings.max_output_tokens, settings.temperature, settings.timeout_seconds) == (3000, -1.0, 180.0)


def test_the_retired_names_are_ignored_in_a_dotenv_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A developer's old OPENAI_* lines in .env neither configure the slice nor fail it."""
    install_openai_files(tmp_path)
    dotenv = tmp_path / ".env"
    dotenv.write_text("\n".join(f"{name}=7" for name in RETIRED_NAMES) + "\n", encoding="utf-8")
    monkeypatch.setitem(OpenAISettings.model_config, "env_file", str(dotenv))

    settings = OpenAISettings()

    assert settings.tenant is None
    assert settings.api_key.get_secret_value() == ""
    assert settings.max_output_tokens == 3000


def test_get_openai_settings_is_cached(tmp_path: Path) -> None:
    """The provider builds the slice once per process."""
    install_openai_files(tmp_path)

    assert get_openai_settings() is get_openai_settings()
