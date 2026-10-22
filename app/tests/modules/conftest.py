"""Shared fixtures for modules test suites."""

from collections.abc import Callable
from typing import Any

import pytest


@pytest.fixture
def set_environment(monkeypatch) -> Callable[[Any, str], None]:
    """Set the environment on a module settings object with consistent monkeypatching."""

    def _set_environment(settings_obj: Any, value: str) -> None:
        monkeypatch.setattr(settings_obj, "environment", value)

    return _set_environment
