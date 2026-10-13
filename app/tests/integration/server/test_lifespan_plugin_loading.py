"""Integration tests for how the lifespan loads feature plugins at boot.

The real lifespan runs on a freshly built plugin manager (the singleton cache
is cleared around each test). Security, directory, Slack provider and feature
registration are stubbed so only plugin loading is observed. Failure cases
swap ``importlib.metadata.distributions`` for a throwaway dist-info
(``tests.fixtures.plugin_dists``): startup must raise before the lifespan
yields, because a feature that cannot load must stop the process instead of
being skipped. The success case reads the real installed metadata and checks
the registered plugin names against the expected feature list.
"""

import importlib.metadata
import sys
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from contracts.plugins.namespace import PLUGIN_NAMESPACE
from server.lifespan import lifespan
from server.plugins.manager import get_plugin_manager
from tests.fixtures.plugin_dists import write_plugin_dist

EXPECTED_PLUGINS = {
    "access.catalog",
    "access.request",
    "access.sync",
    "geolocate",
    "incident.comms",
    "incident.scribe",
    "oncall_sync",
    "rant",
    "user_rotations",
}
RAISING_MODULE = "fake_plugin_raising_i18n"
RAISING_SOURCE = """
from contracts.plugins.namespace import hookimpl


@hookimpl
def register_i18n_resources(registry):
    raise RuntimeError("fake_plugin_i18n_failed")
"""


@pytest.fixture(autouse=True)
def _fresh_plugin_manager() -> Iterator[None]:
    get_plugin_manager.cache_clear()
    yield
    get_plugin_manager.cache_clear()
    sys.modules.pop(RAISING_MODULE, None)


def _stub_startup(stack: ExitStack, *, stub_translation: bool) -> None:
    provider = MagicMock()
    provider.app = None
    stack.enter_context(patch("server.lifespan._initialize_security_services"))
    stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
    stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
    stack.enter_context(patch("server.lifespan.register_feature_integrations"))
    stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))
    if stub_translation:
        stack.enter_context(patch("server.lifespan._initialize_translation_service"))


@pytest.mark.integration
async def test_lifespan_aborts_before_yield_when_an_entry_point_fails_to_import(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dist = write_plugin_dist(tmp_path, PLUGIN_NAMESPACE, {"broken": "fake_plugin_module_that_does_not_exist"})
    monkeypatch.setattr(importlib.metadata, "distributions", lambda: [dist])
    reached_yield = False

    with ExitStack() as stack, pytest.raises(ModuleNotFoundError):
        _stub_startup(stack, stub_translation=True)
        async with lifespan(FastAPI()):
            reached_yield = True

    assert reached_yield is False


@pytest.mark.integration
async def test_lifespan_aborts_before_yield_when_a_hookimpl_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dist = write_plugin_dist(tmp_path, PLUGIN_NAMESPACE, {"raising": RAISING_MODULE}, {RAISING_MODULE: RAISING_SOURCE})
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(importlib.metadata, "distributions", lambda: [dist])
    reached_yield = False

    with ExitStack() as stack, pytest.raises(RuntimeError, match="fake_plugin_i18n_failed"):
        _stub_startup(stack, stub_translation=False)
        async with lifespan(FastAPI()):
            reached_yield = True

    assert reached_yield is False


@pytest.mark.integration
async def test_lifespan_registers_exactly_the_declared_feature_plugins() -> None:
    with ExitStack() as stack:
        _stub_startup(stack, stub_translation=True)
        async with lifespan(FastAPI()):
            pm = get_plugin_manager()
            registered = {pm.get_name(plugin) for plugin, _ in pm.list_plugin_distinfo()}

    assert registered == EXPECTED_PLUGINS
