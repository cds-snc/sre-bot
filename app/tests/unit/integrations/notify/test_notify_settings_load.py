"""Tests for the GC Notify vendor settings slice in integrations/notify/settings.py.

Each test removes the slice's environment variables and ignores the .env file,
so it observes only the values it sets. Field values are asserted by their
environment variable names, which the slice must keep unchanged.
"""

from collections.abc import Iterator

import pytest

from integrations.notify.settings import NotifySettings, get_notify_settings

pytestmark = pytest.mark.unit

_DEFAULTS: dict[str, str | None] = {
    "NOTIFY_SRE_USER_NAME": None,
    "NOTIFY_SRE_CLIENT_SECRET": None,
    "NOTIFY_API_URL": "",
}


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Clear the slice's variables and the cached singleton around each test."""
    for name in _DEFAULTS:
        monkeypatch.delenv(name, raising=False)
    get_notify_settings.cache_clear()
    yield
    get_notify_settings.cache_clear()


def test_notify_settings_getter_returns_one_cached_instance() -> None:
    """The getter is a process-wide singleton: repeated calls return the same object."""
    assert get_notify_settings() is get_notify_settings()


@pytest.mark.parametrize("name", list(_DEFAULTS))
def test_notify_settings_reads_each_field_from_its_env_var(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """Each field reads the environment variable of the same name."""
    monkeypatch.setenv(name, "from-env")

    settings = NotifySettings(_env_file=None)

    assert getattr(settings, name) == "from-env"


def test_notify_settings_defaults_apply_when_unset() -> None:
    """With no variables set, every field holds its documented default."""
    settings = NotifySettings(_env_file=None)

    assert {name: getattr(settings, name) for name in _DEFAULTS} == _DEFAULTS


def test_notify_settings_model_config_reads_dotenv_case_sensitively() -> None:
    """The slice loads .env, matches names case-sensitively and ignores unknown keys."""
    config = NotifySettings.model_config

    assert config.get("env_file") == ".env"
    assert config.get("case_sensitive") is True
    assert config.get("extra") == "ignore"
