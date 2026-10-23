"""The app factory refuses to build a production app with the dev bypass switched on.

ENVIRONMENT is set per test and the identity and security providers are cleared,
so create_app runs the real configuration phase on the checked-in files for that
environment. The security slice is built without the .env file, so only the
SECURITY__ variables a test sets reach it.
"""

from collections.abc import Iterator

import pytest

from contracts.configuration import ConfigurationError
from infrastructure.security.settings import SecuritySettings, get_security_settings
from server import server
from server.configuration import get_identity_settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Only the variables a test sets reach the security slice; the providers rebuild per test."""
    monkeypatch.setitem(SecuritySettings.model_config, "env_file", None)
    for field in SecuritySettings.model_fields:
        monkeypatch.delenv(f"SECURITY__{field.upper()}", raising=False)
    get_identity_settings.cache_clear()
    get_security_settings.cache_clear()
    yield
    get_identity_settings.cache_clear()
    get_security_settings.cache_clear()


@pytest.mark.parametrize(
    ("name", "value", "named"),
    [
        ("SECURITY__DEV_BYPASS_ENABLED", "true", "dev_bypass_enabled"),
        ("SECURITY__DEV_BYPASS_TOKEN", "a-token", "SECURITY__DEV_BYPASS_TOKEN"),
    ],
)
def test_production_with_the_bypass_switched_on_fails_before_building(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str, named: str
) -> None:
    """The bypass flag or a bypass token present in production stops the factory, naming the setting."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv(name, value)

    with pytest.raises(ConfigurationError, match=named):
        server.create_app()


def test_production_with_the_bypass_off_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """With neither the flag nor a token, production builds as usual."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert server.create_app() is not None


def test_local_with_the_bypass_switched_on_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Outside production the bypass may be on; the per-request guards still apply."""
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("SECURITY__DEV_BYPASS_ENABLED", "true")
    monkeypatch.setenv("SECURITY__DEV_BYPASS_TOKEN", "a-token")

    assert server.create_app() is not None
