"""Isolation fixtures for AWS integration unit tests.

Clears cached settings/shield providers and AWS_* environment variables
between tests so that each test observes a clean configuration surface.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from integrations.aws.settings import AWSSettings, get_aws_settings


def _clear_aws_caches() -> None:
    """Reset cached singleton providers used by the AWS shield."""
    get_aws_settings.cache_clear()


def _clear_aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every AWS_* variable so tests cannot read host values."""
    for key in tuple(os.environ):
        if key.startswith("AWS_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _aws_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Apply env + cache isolation for every AWS unit test."""
    monkeypatch.setitem(AWSSettings.model_config, "env_file", None)
    _clear_aws_env(monkeypatch)
    _clear_aws_caches()
    yield
    _clear_aws_caches()
