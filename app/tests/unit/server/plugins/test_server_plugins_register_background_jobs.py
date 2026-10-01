"""Unit tests for server.plugins.manager.register_background_jobs.

A real cached plugin manager (cleared before and after) gets one in-test plugin
whose hookimpl records the registry it receives, so the helper is exercised
through pluggy rather than a mock. The registry is a plain sentinel: the helper
must hand it to the hook untouched.
"""

from collections.abc import Iterator

import pytest

from contracts.plugins.namespace import hookimpl
from contracts.scheduler.registry import BackgroundJobRegistry
from server.plugins.manager import get_plugin_manager, register_background_jobs

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _fresh_plugin_manager() -> Iterator[None]:
    get_plugin_manager.cache_clear()
    yield
    get_plugin_manager.cache_clear()


def test_helper_fires_the_hook_once_with_the_registry_it_is_given() -> None:
    received: list[object] = []

    class Plugin:
        @hookimpl
        def register_background_jobs(self, registry: BackgroundJobRegistry) -> None:
            received.append(registry)

    get_plugin_manager().register(Plugin())
    registry = object()

    register_background_jobs(registry)  # type: ignore[arg-type]

    assert received == [registry]


def test_helper_is_a_no_op_when_no_plugin_implements_the_hook() -> None:
    register_background_jobs(object())  # type: ignore[arg-type]

    assert get_plugin_manager().get_plugins() == set()
