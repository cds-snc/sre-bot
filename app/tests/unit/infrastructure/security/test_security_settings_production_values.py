"""The values the checked-in configuration files give the security slice in each environment.

Each test installs the real base file and one environment file and builds the
slice with no .env file and no SECURITY__ variable, so it sees exactly what a
task started with that ENVIRONMENT would read. Production must keep the values
it ran with before the slice moved to the files: one trusted issuer with an
https key set, asymmetric algorithms and an audience, no CORS origin, the
default methods and headers, and the dev bypass off with no token.
"""

import tomllib
from collections.abc import Iterator

import pytest

from contracts.configuration import install_configuration_files
from infrastructure.security.settings import ASYMMETRIC_ALGORITHMS, SecuritySettings
from server.configuration import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit

_ENVIRONMENTS = ("local", "ci", "production")


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No SECURITY__ variable reaches the slice, so only the files decide."""
    for field in SecuritySettings.model_fields:
        monkeypatch.delenv(f"SECURITY__{field.upper()}", raising=False)
    yield


def _settings_for(environment: str) -> SecuritySettings:
    install_configuration_files(load_configuration_files(environment))
    return SecuritySettings(_env_file=None)


def test_production_trusts_exactly_one_issuer() -> None:
    """Production keeps its single issuer, with an https key set, asymmetric algorithms and an audience."""
    settings = _settings_for("production")

    assert len(settings.issuers) == 1
    entry = settings.issuers[0]
    assert entry.issuer.startswith("https://")
    assert entry.jwks_uri.startswith("https://")
    assert entry.algorithms
    assert set(entry.algorithms) <= ASYMMETRIC_ALGORITHMS
    assert entry.audience


def test_production_cors_policy_is_unchanged() -> None:
    """Production allows no browser origin, and only the methods and headers the API serves."""
    settings = _settings_for("production")

    assert settings.cors_allowed_origins == []
    assert settings.cors_allowed_methods == ["GET", "POST"]
    assert settings.cors_allowed_headers == ["Authorization", "Content-Type", "X-Request-ID", "traceparent"]


@pytest.mark.parametrize("environment", _ENVIRONMENTS)
def test_dev_bypass_is_off_in_every_environment_file(environment: str) -> None:
    """No checked-in file turns the dev bypass on; a developer opts in through their own .env."""
    settings = _settings_for(environment)

    assert settings.dev_bypass_enabled is False
    assert settings.dev_bypass_token is None


@pytest.mark.parametrize("environment", ("local", "ci"))
def test_non_production_files_trust_no_issuer(environment: str) -> None:
    """Local and ci trust no issuer from the files; a developer adds the local token server through .env."""
    assert _settings_for(environment).issuers == []


def test_no_configuration_file_holds_the_bypass_token() -> None:
    """The bypass token is a secret: no file under app/config sets it in any table."""
    for path in sorted(CONFIG_DIR.glob("*.toml")):
        security = tomllib.loads(path.read_text(encoding="utf-8")).get("security", {})

        assert "dev_bypass_token" not in security, path
