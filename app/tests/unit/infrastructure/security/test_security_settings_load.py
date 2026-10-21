"""Tests for the security settings slice in infrastructure/security/settings.py.

Each test removes the slice's environment variables and ignores the .env file,
so it observes only the values it sets. Field values are asserted by their
environment variable names, which the slice must keep unchanged. The validator
tests build the slice from keyword arguments and assert the ValidationError
names the offending key.
"""

import json
from collections.abc import Iterator

import pytest
from pydantic import SecretStr, ValidationError

from infrastructure.configuration.app import AppSettings
from infrastructure.configuration.infrastructure.server import ServerSettings
from infrastructure.security.settings import SecuritySettings, get_security_settings

pytestmark = pytest.mark.unit

_NAMES = (
    "ISSUER_CONFIG",
    "CORS_ALLOWED_ORIGINS",
    "CORS_ALLOWED_METHODS",
    "CORS_ALLOWED_HEADERS",
    "DEV_BYPASS_ENABLED",
    "DEV_BYPASS_TOKEN",
)

_ISSUER = {
    "issuer-1": {
        "jwks_uri": "https://issuer.example.com/.well-known/jwks.json",
        "algorithms": ["RS256"],
        "audience": "aud-1",
    }
}


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Clear the slice's variables and the cached singleton around each test."""
    for name in _NAMES:
        monkeypatch.delenv(name, raising=False)
    get_security_settings.cache_clear()
    yield
    get_security_settings.cache_clear()


def test_security_settings_getter_returns_one_cached_instance() -> None:
    """The getter is a process-wide singleton: repeated calls return the same object."""
    assert get_security_settings() is get_security_settings()


def test_security_settings_reads_each_field_from_its_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each field reads the environment variable of the same name; lists and the issuer map are JSON."""
    monkeypatch.setenv("ISSUER_CONFIG", json.dumps(_ISSUER))
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://frontend.example"]')
    monkeypatch.setenv("CORS_ALLOWED_METHODS", '["GET"]')
    monkeypatch.setenv("CORS_ALLOWED_HEADERS", '["Authorization"]')
    monkeypatch.setenv("DEV_BYPASS_ENABLED", "true")
    monkeypatch.setenv("DEV_BYPASS_TOKEN", "dev-token")

    settings = SecuritySettings(_env_file=None)

    assert settings.issuer_config == _ISSUER
    assert settings.cors_allowed_origins == ["https://frontend.example"]
    assert settings.cors_allowed_methods == ["GET"]
    assert settings.cors_allowed_headers == ["Authorization"]
    assert settings.dev_bypass_enabled is True
    assert settings.dev_bypass_token is not None
    assert settings.dev_bypass_token.get_secret_value() == "dev-token"


def test_security_settings_defaults_apply_when_unset() -> None:
    """With no variables set: an empty issuer map, no origins, GET and POST only, the bypass off and no token."""
    settings = SecuritySettings(_env_file=None)

    assert settings.issuer_config == {}
    assert settings.cors_allowed_origins == []
    assert settings.cors_allowed_methods == ["GET", "POST"]
    assert settings.cors_allowed_headers == ["Authorization", "Content-Type", "X-Request-ID", "traceparent"]
    assert settings.dev_bypass_enabled is False
    assert settings.dev_bypass_token is None


def test_security_settings_unparseable_issuer_config_env_yields_empty_map(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-JSON ISSUER_CONFIG value (as the pytest env sets) degrades to no issuers rather than failing."""
    monkeypatch.setenv("ISSUER_CONFIG", "test-issuer-config")

    settings = SecuritySettings(_env_file=None)

    assert settings.issuer_config == {}


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("CORS_ALLOWED_ORIGINS", ["*"]),
        ("CORS_ALLOWED_ORIGINS", ["*", "https://frontend.example"]),
        ("CORS_ALLOWED_METHODS", ["*"]),
        ("CORS_ALLOWED_HEADERS", ["*"]),
    ],
)
def test_security_settings_cors_wildcard_raises_naming_the_key(key: str, value: list[str]) -> None:
    """A wildcard in any CORS list fails construction, and the error names the list."""
    with pytest.raises(ValidationError, match=key):
        SecuritySettings(_env_file=None, **{key: value})


def test_security_settings_issuer_without_audience_raises_naming_the_issuer() -> None:
    """An issuer entry without an audience fails construction, and the error names the issuer."""
    issuer = {"issuer-1": {"jwks_uri": "https://issuer.example.com/.well-known/jwks.json"}}

    with pytest.raises(ValidationError, match="ISSUER_CONFIG entry for issuer 'issuer-1'"):
        SecuritySettings(_env_file=None, ISSUER_CONFIG=issuer)


def test_security_settings_dev_bypass_token_is_masked() -> None:
    """The bypass token is a SecretStr: its value never shows in repr or JSON output."""
    settings = SecuritySettings(_env_file=None, DEV_BYPASS_TOKEN=SecretStr("dev-token-value"))

    assert "dev-token-value" not in repr(settings)
    assert "dev-token-value" not in settings.model_dump_json()


def test_security_settings_model_config_reads_dotenv_case_insensitively() -> None:
    """The slice loads .env, matches names case-insensitively and ignores unknown keys."""
    config = SecuritySettings.model_config

    assert config.get("env_file") == ".env"
    assert config.get("case_sensitive") is False
    assert config.get("extra") == "ignore"


@pytest.mark.parametrize("name", _NAMES)
def test_security_keys_are_declared_only_by_the_security_slice(name: str) -> None:
    """AppSettings and ServerSettings no longer declare any security key."""
    assert name.lower() in SecuritySettings.model_fields
    assert name not in AppSettings.model_fields
    assert name not in ServerSettings.model_fields
