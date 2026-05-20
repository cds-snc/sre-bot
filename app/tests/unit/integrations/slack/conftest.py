"""Isolation fixtures for Slack integration unit tests.

Clears cached settings/shield providers and SLACK_* environment variables
between tests so that each test observes a clean configuration surface.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from integrations.slack.settings import SlackSettings, get_slack_settings


def _clear_slack_caches() -> None:
    """Reset cached singleton providers used by the Slack shield."""
    get_slack_settings.cache_clear()


def _clear_slack_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every SLACK_* variable so tests cannot read host values."""
    for key in tuple(os.environ):
        if key.startswith("SLACK_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _slack_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply env + cache isolation for every Slack unit test."""
    monkeypatch.setitem(SlackSettings.model_config, "env_file", None)
    _clear_slack_env(monkeypatch)
    _clear_slack_caches()
    yield
    _clear_slack_caches()
