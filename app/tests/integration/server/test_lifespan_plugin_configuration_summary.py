"""Integration tests for the plugin_configuration_summary event.

The real lifespan runs on a freshly built plugin manager whose entry points come from a
throwaway dist-info (``tests.fixtures.plugin_dists``), swapped in after the configuration
phase has run on the real metadata. Core services, security, the directory, the Slack
provider and translation are stubbed; feature registration runs for real. The fake
plugins build the access permission-sets slice, which no host slice getter builds, or a
subclass of it, in their startup_warmup. The event must list only slices first built
during a plugin's boot, grouped under the plugin that built them, with a hash per
entry, and a canary non-public value must appear only as its last four characters.
"""

import dataclasses
import importlib.metadata
import sys
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from structlog.testing import capture_logs

from contracts.plugins.namespace import PLUGIN_NAMESPACE
from packages.access.common.settings import get_access_permission_sets_settings
from server.configuration import load_host_configuration
from server.lifespan import build_lifespan
from server.plugins.manager import get_plugin_manager
from tests.fixtures.plugin_dists import write_plugin_dist

pytestmark = pytest.mark.integration

ALPHA_MODULE = "fake_plugin_builds_access_slice"
ALPHA_SOURCE = """
from contracts.plugins.namespace import hookimpl
from packages.access.common.settings import get_access_permission_sets_settings


@hookimpl
def startup_warmup(logger):
    get_access_permission_sets_settings()
"""
BETA_MODULE = "fake_plugin_builds_access_subclass"
BETA_SOURCE = """
from contracts.plugins.namespace import hookimpl
from packages.access.common.settings import AccessPermissionSetsSettings


class BetaSettings(AccessPermissionSetsSettings):
    pass


@hookimpl
def startup_warmup(logger):
    BetaSettings()
"""
IDLE_MODULE = "fake_plugin_builds_nothing"
IDLE_SOURCE = """
from contracts.plugins.namespace import hookimpl
from infrastructure.security.settings import get_security_settings


@hookimpl
def startup_warmup(logger):
    get_security_settings()
"""
MODULES = {ALPHA_MODULE: ALPHA_SOURCE, BETA_MODULE: BETA_SOURCE, IDLE_MODULE: IDLE_SOURCE}
ENTRY_POINTS = {"alpha": ALPHA_MODULE, "beta": BETA_MODULE, "idle": IDLE_MODULE}
NON_PUBLIC = "arn:aws:sso:::permissionSet/ssoins-canary0001/ps-0001"


@pytest.fixture(autouse=True)
def _fresh_plugin_manager(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ACCESS_PERMISSION_SETS__SYSTEM_ADMIN_PERMISSIONS", NON_PUBLIC)
    get_access_permission_sets_settings.cache_clear()
    get_plugin_manager.cache_clear()
    yield
    get_plugin_manager.cache_clear()
    get_access_permission_sets_settings.cache_clear()
    for module in MODULES:
        sys.modules.pop(module, None)


def _install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dist = write_plugin_dist(tmp_path, PLUGIN_NAMESPACE, ENTRY_POINTS, MODULES)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(importlib.metadata, "distributions", lambda: [dist])


def _stub_startup(stack: ExitStack) -> None:
    provider = MagicMock()
    provider.app = None
    stack.enter_context(patch("server.lifespan.initialize_core_services"))
    stack.enter_context(patch("server.lifespan._initialize_security_services"))
    stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
    stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
    stack.enter_context(patch("server.lifespan._initialize_translation_service"))
    stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))


async def _boot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, disabled: frozenset[str] = frozenset()) -> list[dict[str, Any]]:
    configuration = load_host_configuration()
    _install(monkeypatch, tmp_path)
    configuration = dataclasses.replace(configuration, disabled_plugins=disabled)
    with ExitStack() as stack, capture_logs() as events:
        _stub_startup(stack)
        async with build_lifespan(configuration)(FastAPI()):
            pass
    return [event for event in events if event["event"] in {"plugin_configuration_summary", "configuration_slice"}]


def _summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    (summary,) = [event for event in events if event["event"] == "plugin_configuration_summary"]
    return summary


async def test_sections_list_only_slices_built_during_each_plugin_boot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Each plugin's entry names the slices it built first; a slice the host phase built is in none."""
    event = _summary(await _boot(monkeypatch, tmp_path))

    sections = {section["plugin"]: section for section in event["plugins"]}
    assert list(sections) == ["alpha", "beta"]
    for section in sections.values():
        assert set(section["slices"]) == {"access_permission_sets"}
        assert len(section["config_hash"]) == 64
    assert event["phase"] == "plugin_boot"


async def test_a_non_public_value_appears_only_as_its_last_four_characters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The canary permission-set ARN is withheld: its tail under partial in the plugin's slice event, never in full."""
    events = await _boot(monkeypatch, tmp_path)

    slice_events = [event for event in events if event["event"] == "configuration_slice"]
    assert {(event["plugin"], event["slice"]) for event in slice_events} == {
        ("alpha", "access_permission_sets"),
        ("beta", "access_permission_sets"),
    }
    assert all(event["phase"] == "plugin_boot" for event in slice_events)
    assert slice_events[0]["partial"]["system_admin_permissions"] == NON_PUBLIC[-4:]
    assert NON_PUBLIC not in repr(events)


async def test_a_disabled_plugin_has_no_section(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A disabled plugin's boot never runs, so its slice is never built and never listed."""
    events = await _boot(monkeypatch, tmp_path, disabled=frozenset({"alpha", "beta"}))
    event = _summary(events)
    assert [event for event in events if event["event"] == "configuration_slice"] == []

    assert event["plugins"] == []
