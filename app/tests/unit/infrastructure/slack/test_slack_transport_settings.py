"""Behavior tests for Slack transport settings slice.

These tests intentionally encode TASK-45.1 behavior before implementation.
"""

from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear transport env var so each test controls it explicitly."""
    monkeypatch.delenv("SLACK__COMMAND_PREFIX", raising=False)


@pytest.fixture(autouse=True)
def _clear_provider_cache() -> None:
    """Keep singleton cache deterministic across test cases."""
    try:
        settings_module = importlib.import_module("infrastructure.slack.settings")
    except ModuleNotFoundError:
        return

    settings_module.get_slack_transport_settings.cache_clear()


def _load_transport_settings_module():
    """Load transport settings module with a clear failure message."""
    try:
        return importlib.import_module("infrastructure.slack.settings")
    except ModuleNotFoundError:
        pytest.fail(
            "Expected infrastructure.slack.settings to exist for TASK-45.1",
            pytrace=False,
        )


@pytest.mark.unit
def test_slack_transport_settings_default_command_prefix_is_empty() -> None:
    """Default COMMAND_PREFIX should be empty when env var is unset."""
    settings_module = _load_transport_settings_module()

    settings = settings_module.SlackTransportSettings()

    assert settings.COMMAND_PREFIX == ""


@pytest.mark.unit
def test_slack_transport_settings_reads_env_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SLACK__COMMAND_PREFIX env var should map to COMMAND_PREFIX."""
    settings_module = _load_transport_settings_module()

    monkeypatch.setenv("SLACK__COMMAND_PREFIX", "dev-")

    settings = settings_module.SlackTransportSettings()

    assert settings.COMMAND_PREFIX == "dev-"


@pytest.mark.unit
def test_get_slack_transport_settings_returns_singleton_instance() -> None:
    """Provider should return the same settings instance per process."""
    settings_module = _load_transport_settings_module()

    first = settings_module.get_slack_transport_settings()
    second = settings_module.get_slack_transport_settings()

    assert first is second


@pytest.mark.unit
def test_slack_transport_settings_invalid_value_fails_validation() -> None:
    """Invalid config should fail fast with Pydantic validation error."""
    settings_module = _load_transport_settings_module()

    with pytest.raises(ValidationError):
        settings_module.SlackTransportSettings(COMMAND_PREFIX=None)
