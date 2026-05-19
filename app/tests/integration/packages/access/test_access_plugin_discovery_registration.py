"""Regression tests for access plugin discovery and registration chain."""

import importlib

import pytest

from infrastructure.plugins.base import auto_discover_plugins
from infrastructure.plugins.manager import get_plugin_manager


_ACCESS_ENV_KEYS = (
    "ACCESS_SYNC_ENABLED",
    "ACCESS_REQUESTS_ENABLED",
    "ACCESS_CATALOG_ENABLED",
    "ACCESS_CONFIG_SOURCE",
    "ACCESS_CONFIG_REF",
    "ACCESS_CONFIG_ENV_DIR_PREFIX",
    "ACCESS_CONFIG_ENV_DIR_SEPARATOR",
    "ACCESS_CONFIG_ENV_PLATFORMS_JSON",
)


@pytest.fixture(autouse=True)
def _isolate_access_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests do not depend on externally provided access env vars."""
    for key in _ACCESS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


class _FakeApp:
    def __init__(self) -> None:
        self.routers: list[object] = []

    def include_router(self, router, prefix: str = "") -> None:
        _ = prefix
        self.routers.append(router)


class _FakeSlackProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def register_command(self, command: str, **kwargs) -> None:
        self.calls.append((command, kwargs.get("parent")))


def test_access_plugins_register_routes_and_slack_commands_from_interactions() -> None:
    """Access plugins should remain discoverable and register interactions endpoints."""
    get_plugin_manager.cache_clear()
    pm = get_plugin_manager()
    auto_discover_plugins(pm, base_paths=["packages"])

    app = _FakeApp()
    slack_provider = _FakeSlackProvider()

    pm.hook.register_routes(app=app)
    pm.hook.register_slack_commands(provider=slack_provider)

    expected_routers = [
        importlib.import_module("packages.access.catalog.interactions.http").router,
        importlib.import_module("packages.access.request.interactions.http").router,
        importlib.import_module("packages.access.sync.interactions.http").router,
    ]

    assert all(router in app.routers for router in expected_routers)
    assert ("sync", "sre.access") in slack_provider.calls

    get_plugin_manager.cache_clear()
