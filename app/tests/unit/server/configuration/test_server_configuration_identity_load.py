"""Unit tests for the env-only identity slice: ENVIRONMENT and GIT_SHA from the process environment."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from server.configuration import IdentitySettings, get_identity_settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start without either name and with an empty provider cache."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("GIT_SHA", raising=False)
    get_identity_settings.cache_clear()


def test_reads_environment_and_git_sha_from_the_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both names come from the process environment."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("GIT_SHA", "deadbeef")

    settings = IdentitySettings()

    assert (settings.environment, settings.git_sha) == ("production", "deadbeef")


def test_git_sha_defaults_to_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """A process without GIT_SHA reports Unknown."""
    monkeypatch.setenv("ENVIRONMENT", "local")

    assert IdentitySettings().git_sha == "Unknown"


def test_env_file_value_is_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A .env file in the working directory never supplies ENVIRONMENT."""
    (tmp_path / ".env").write_text("ENVIRONMENT=local\n")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValidationError) as exc_info:
        IdentitySettings()

    assert exc_info.value.errors()[0]["loc"] == ("environment",)


def test_missing_environment_names_the_field() -> None:
    """Without ENVIRONMENT, construction fails naming the field."""
    with pytest.raises(ValidationError) as exc_info:
        IdentitySettings()

    assert exc_info.value.errors()[0]["type"] == "missing"
    assert exc_info.value.errors()[0]["loc"] == ("environment",)


def test_unknown_environment_name_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A value without a configuration file, such as the rollback rehearsal's, fails boot."""
    monkeypatch.setenv("ENVIRONMENT", "rollback-rehearsal")

    with pytest.raises(ValidationError, match="environment"):
        IdentitySettings()


def test_lower_case_names_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lower-case spelling of the names is read too."""
    monkeypatch.setenv("environment", "ci")
    monkeypatch.setenv("git_sha", "abc")

    settings = IdentitySettings()

    assert (settings.environment, settings.git_sha) == ("ci", "abc")


def test_provider_returns_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """The provider caches the identity for the process."""
    monkeypatch.setenv("ENVIRONMENT", "ci")

    assert get_identity_settings() is get_identity_settings()
