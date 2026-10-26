"""Unit tests for load_plugins in server.plugins.manager.

Each test builds a fresh plugin manager on the contracts namespace and swaps
``importlib.metadata.distributions`` for a throwaway dist-info written under
``tmp_path`` (``tests.fixtures.plugin_dists``), so the real pluggy entry-point
loader runs against known metadata and never imports a first-party feature.
Assertions check the registered plugin names and that loader errors propagate
unchanged, because boot must stop on them. A disabled entry point targets a
module whose source raises on import, so a passing test proves the loader never
imported it (and so never read its settings or called its hookimpls).
"""

import importlib.metadata
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pluggy
import pytest

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from server.plugins.manager import installed_plugin_names, load_plugins
from tests.fixtures.plugin_dists import write_plugin_dist

pytestmark = pytest.mark.unit

FAKE_MODULE = "fake_plugin_loader_demo"
POISONED_MODULE = "fake_plugin_loader_poisoned"


@pytest.fixture
def pm() -> pluggy.PluginManager:
    manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    manager.add_hookspecs(FeatureLifecycleSpecs)
    return manager


@pytest.fixture(autouse=True)
def _forget_fake_module() -> Iterator[None]:
    yield
    sys.modules.pop(FAKE_MODULE, None)
    sys.modules.pop(POISONED_MODULE, None)


def _install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, entry_points: dict[str, str]) -> None:
    modules = {FAKE_MODULE: "VALUE = 1\n", POISONED_MODULE: "raise RuntimeError('a disabled plugin was imported')\n"}
    dist = write_plugin_dist(tmp_path, PLUGIN_NAMESPACE, entry_points, modules)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(importlib.metadata, "distributions", lambda: [dist])


def test_load_plugins_registers_each_entry_point_under_its_name(
    pm: pluggy.PluginManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install(monkeypatch, tmp_path, {"demo.sub": FAKE_MODULE})
    logger = MagicMock()

    load_plugins(pm, (), logger)

    assert pm.get_plugin("demo.sub") is sys.modules[FAKE_MODULE]
    logger.info.assert_called_once_with("feature_plugins_loaded", plugins=["demo.sub"], disabled=[])


def test_a_disabled_entry_point_is_never_imported_or_registered(
    pm: pluggy.PluginManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install(monkeypatch, tmp_path, {"demo.sub": FAKE_MODULE, "demo.off": POISONED_MODULE})
    logger = MagicMock()

    load_plugins(pm, ["demo.off"], logger)

    assert POISONED_MODULE not in sys.modules
    assert pm.get_plugin("demo.off") is None
    assert pm.is_blocked("demo.off")
    logger.info.assert_called_once_with("feature_plugins_loaded", plugins=["demo.sub"], disabled=["demo.off"])


def test_every_entry_point_disabled_still_boots_with_no_plugin(
    pm: pluggy.PluginManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install(monkeypatch, tmp_path, {"demo.off": POISONED_MODULE})
    logger = MagicMock()

    load_plugins(pm, ["demo.off"], logger)

    assert POISONED_MODULE not in sys.modules
    logger.info.assert_called_once_with("feature_plugins_loaded", plugins=[], disabled=["demo.off"])


def test_load_plugins_raises_when_the_group_declares_no_entry_point(
    pm: pluggy.PluginManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(importlib.metadata, "distributions", lambda: [])

    with pytest.raises(RuntimeError, match="no_plugin_entry_points"):
        load_plugins(pm, (), MagicMock())


def test_installed_plugin_names_reads_the_group_without_importing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch, tmp_path, {"demo.sub": FAKE_MODULE, "demo.off": POISONED_MODULE})

    assert installed_plugin_names() == ["demo.off", "demo.sub"]
    assert POISONED_MODULE not in sys.modules


def test_load_plugins_propagates_an_entry_point_that_fails_to_import(
    pm: pluggy.PluginManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install(monkeypatch, tmp_path, {"broken": "fake_plugin_module_that_does_not_exist"})

    with pytest.raises(ModuleNotFoundError):
        load_plugins(pm, (), MagicMock())


def test_load_plugins_twice_keeps_one_registration_per_entry_point(
    pm: pluggy.PluginManager, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install(monkeypatch, tmp_path, {"demo.sub": FAKE_MODULE})

    load_plugins(pm, (), MagicMock())
    load_plugins(pm, (), MagicMock())

    assert [pm.get_name(plugin) for plugin, _ in pm.list_plugin_distinfo()] == ["demo.sub"]
