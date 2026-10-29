"""Tests for the security settings slice on the [security] table.

Each test removes the slice's SECURITY__ environment variables and builds the
slice without the .env file under the installed ci configuration files, so it
observes only the files and the values it sets. Validator tests assert the error names the offending key.
"""

import json
from collections.abc import Iterator

import pytest
from pydantic import SecretStr

from contracts.configuration import ConfigurationError, ConfigurationSlice
from infrastructure.security.settings import SecuritySettings, get_security_settings
from server.configuration import IdentitySettings, ServerSettings

pytestmark = pytest.mark.unit

_FIELDS = (
    "issuers",
    "cors_allowed_origins",
    "cors_allowed_methods",
    "cors_allowed_headers",
    "dev_bypass_enabled",
    "dev_bypass_token",
)

_ISSUER = {
    "issuer": "https://issuer.example.com",
    "jwks_uri": "https://issuer.example.com/.well-known/jwks.json",
    "algorithms": ["RS256"],
    "audience": "aud-1",
}


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Clear the slice's variables and the cached singleton around each test."""
    for field in _FIELDS:
        monkeypatch.delenv(f"SECURITY__{field.upper()}", raising=False)
    get_security_settings.cache_clear()
    yield
    get_security_settings.cache_clear()


def test_security_settings_getter_returns_one_cached_instance() -> None:
    """The getter is a process-wide singleton: repeated calls return the same object."""
    assert get_security_settings() is get_security_settings()


def test_security_settings_is_a_slice_on_the_security_table() -> None:
    """The slice reads the [security] table with the SECURITY__ prefix and rejects unknown keys."""
    config = SecuritySettings.model_config

    assert issubclass(SecuritySettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("security",)
    assert config.get("env_prefix") == "SECURITY__"
    assert config.get("extra") == "forbid"


@pytest.mark.parametrize("field", _FIELDS)
def test_security_settings_fields_have_no_alias(field: str) -> None:
    """Every field is read only under its SECURITY__<FIELD> name: no alias widens it."""
    info = SecuritySettings.model_fields[field]

    assert info.alias is None
    assert info.validation_alias is None


def test_security_settings_defaults_come_from_the_base_file() -> None:
    """Under the ci files: no issuers, no origins, GET and POST only, the default headers, the bypass off and no token."""
    settings = SecuritySettings(_env_file=None)

    assert settings.issuers == []
    assert settings.issuer_config == {}
    assert settings.cors_allowed_origins == []
    assert settings.cors_allowed_methods == ["GET", "POST"]
    assert settings.cors_allowed_headers == ["Authorization", "Content-Type", "X-Request-ID", "traceparent"]
    assert settings.dev_bypass_enabled is False
    assert settings.dev_bypass_token is None


def test_security_settings_reads_each_field_from_its_prefixed_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each SECURITY__<FIELD> variable beats the file value; lists and the issuer list are JSON."""
    monkeypatch.setenv("SECURITY__ISSUERS", json.dumps([_ISSUER]))
    monkeypatch.setenv("SECURITY__CORS_ALLOWED_ORIGINS", '["https://frontend.example"]')
    monkeypatch.setenv("SECURITY__CORS_ALLOWED_METHODS", '["GET"]')
    monkeypatch.setenv("SECURITY__CORS_ALLOWED_HEADERS", '["Authorization"]')
    monkeypatch.setenv("SECURITY__DEV_BYPASS_ENABLED", "true")
    monkeypatch.setenv("SECURITY__DEV_BYPASS_TOKEN", "dev-token")

    settings = SecuritySettings(_env_file=None)

    assert settings.issuer_config == {
        "https://issuer.example.com": {
            "jwks_uri": "https://issuer.example.com/.well-known/jwks.json",
            "algorithms": ["RS256"],
            "audience": "aud-1",
        }
    }
    assert settings.cors_allowed_origins == ["https://frontend.example"]
    assert settings.cors_allowed_methods == ["GET"]
    assert settings.cors_allowed_headers == ["Authorization"]
    assert settings.dev_bypass_enabled is True
    assert settings.dev_bypass_token is not None
    assert settings.dev_bypass_token.get_secret_value() == "dev-token"


def test_security_settings_reads_the_bypass_token_from_the_dotenv_file(tmp_path, monkeypatch) -> None:
    """A developer's .env carries SECURITY__DEV_BYPASS_TOKEN; it reaches the field as a secret."""
    env_file = tmp_path / ".env"
    env_file.write_text("SECURITY__DEV_BYPASS_TOKEN=dotenv-token\n")

    settings = SecuritySettings(_env_file=env_file)

    assert settings.dev_bypass_token is not None
    assert settings.dev_bypass_token.get_secret_value() == "dotenv-token"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("cors_allowed_origins", ["*"]),
        ("cors_allowed_origins", ["*", "https://frontend.example"]),
        ("cors_allowed_methods", ["*"]),
        ("cors_allowed_headers", ["*"]),
    ],
)
def test_security_settings_cors_wildcard_raises_naming_the_key(field: str, value: list[str]) -> None:
    """A wildcard in any CORS list fails construction, and the error names the list."""
    with pytest.raises(ConfigurationError, match=field):
        SecuritySettings(_env_file=None, **{field: value})


def test_security_settings_dev_bypass_token_is_masked() -> None:
    """The bypass token is a SecretStr: its value never shows in repr or JSON output."""
    settings = SecuritySettings(_env_file=None, dev_bypass_token=SecretStr("dev-token-value"))

    assert "dev-token-value" not in repr(settings)
    assert "dev-token-value" not in settings.model_dump_json()


@pytest.mark.parametrize("field", _FIELDS)
def test_security_keys_are_declared_only_by_the_security_slice(field: str) -> None:
    """The identity and [server] slices do not declare any security key."""
    assert field in SecuritySettings.model_fields
    assert field not in IdentitySettings.model_fields
    assert field not in ServerSettings.model_fields
