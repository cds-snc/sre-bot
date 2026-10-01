"""Unit tests for the host plugin manager in server.plugins.manager.

The real cached manager is built (the cache is cleared before and after, so no
state leaks between tests) and inspected: it must be one instance per process,
carry the contracts namespace, and expose every lifecycle hookspec.
"""

from collections.abc import Iterator

import pytest

from contracts.plugins.namespace import PLUGIN_NAMESPACE
from server.plugins.manager import get_plugin_manager

pytestmark = pytest.mark.unit

EXPECTED_HOOKS = [
    "register_slack_commands",
    "register_routes",
    "register_i18n_resources",
    "register_event_handlers",
    "register_background_jobs",
    "startup_warmup",
]


@pytest.fixture(autouse=True)
def _fresh_plugin_manager() -> Iterator[None]:
    get_plugin_manager.cache_clear()
    yield
    get_plugin_manager.cache_clear()


def test_plugin_manager_is_a_process_wide_singleton() -> None:
    assert get_plugin_manager() is get_plugin_manager()


def test_plugin_manager_is_built_from_the_contracts_namespace() -> None:
    assert get_plugin_manager().project_name == PLUGIN_NAMESPACE


def test_plugin_manager_carries_every_lifecycle_hookspec() -> None:
    hook = get_plugin_manager().hook

    assert all(hasattr(hook, name) for name in EXPECTED_HOOKS)
