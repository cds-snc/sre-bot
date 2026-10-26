"""Boot tests for plugin enablement against the checked-in files and the installed entry points.

The real base.toml (installed with ci.toml by the autouse fixture) is checked
against the entry points of the installed distribution, so a plugin added
without its key, or a key left behind, fails here before it fails a deploy. A
fresh plugin manager loads with the ci disabled names and mounts routes on a
real FastAPI app, so the assertions read the registered plugins, the route
table and the OpenAPI schema a client would see. The import-linter
protected-plugins contract is read from pyproject.toml and must list exactly the
entry-point modules, or a new plugin could be imported by host code unnoticed.
"""

import importlib
import tomllib
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pluggy
import pytest
from fastapi import FastAPI

import server.plugins
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from server.configuration import CONFIG_DIR
from server.plugins.manager import installed_plugin_names, load_plugins
from server.plugins.settings import PluginsSettings, check_plugin_enablement, get_plugins_settings

pytestmark = pytest.mark.integration

APP_ROOT = Path(server.plugins.__file__).resolve().parents[2]
ACCESS_PLUGINS = frozenset({"access.catalog", "access.request", "access.sync"})
ACCESS_ROUTER_MODULES = (
    "packages.access.catalog.interactions.http",
    "packages.access.request.interactions.http",
    "packages.access.sync.interactions.http",
)


@pytest.fixture(autouse=True)
def _checked_in_values_only(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep a developer's PLUGINS__ variables and app/.env out of the slice."""
    for area in ("INCIDENT_RESPONSE", "CLOUD_OPERATIONS", "PLATFORM_ACCESS", "WORKPLACE_UTILITIES"):
        monkeypatch.delenv(f"PLUGINS__{area}", raising=False)
    monkeypatch.setitem(PluginsSettings.model_config, "env_file", None)
    get_plugins_settings.cache_clear()
    yield
    get_plugins_settings.cache_clear()


def _pyproject() -> dict:
    return tomllib.loads((APP_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_every_installed_entry_point_has_exactly_one_key_in_base() -> None:
    check_plugin_enablement(get_plugins_settings(), installed_plugin_names())


def test_base_keeps_the_access_plugins_off_and_every_other_plugin_on() -> None:
    base = tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))
    keys = {name: enabled for area in base["plugins"].values() for name, enabled in area.items()}

    assert {name for name, enabled in keys.items() if not enabled} == ACCESS_PLUGINS
    assert get_plugins_settings().disabled() == ACCESS_PLUGINS


def test_disabled_access_plugins_register_no_route_and_no_openapi_path() -> None:
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    app = FastAPI()

    load_plugins(pm, get_plugins_settings().disabled(), MagicMock())
    pm.hook.register_routes(app=app)

    assert ACCESS_PLUGINS.isdisjoint(name for name, plugin in pm.list_name_plugin() if plugin is not None)
    access_paths = {route.path for module in ACCESS_ROUTER_MODULES for route in importlib.import_module(module).router.routes}
    assert access_paths
    mounted = {getattr(route, "path", "") for route in app.routes}
    assert not any(path.endswith(access) for path in mounted for access in access_paths)
    assert not any(path.endswith(access) for path in app.openapi()["paths"] for access in access_paths)


def test_the_protected_plugins_contract_lists_exactly_the_entry_point_modules() -> None:
    pyproject = _pyproject()
    entry_point_modules = set(pyproject["project"]["entry-points"][PLUGIN_NAMESPACE].values())
    contract = next(c for c in pyproject["tool"]["importlinter"]["contracts"] if c.get("id") == "protected-plugins")

    assert set(contract["protected_modules"]) == entry_point_modules
