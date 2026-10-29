"""Integration tests for the boot failure event of an enabled plugin.

The real lifespan runs on a freshly built plugin manager whose entry points come
from a throwaway dist-info (``tests.fixtures.plugin_dists``), swapped in after the
configuration phase has run on the real metadata. Core services, security, the
directory, the Slack provider and translation are stubbed; feature registration runs
for real so a raising ``startup_warmup`` is observed. ``capture_logs`` records the
events. Each failure must stop startup before the lifespan yields and log exactly one
CRITICAL ``plugin_boot_failed`` naming the plugin, the phase, the error type and the
setting at fault, with no other field, so no configured value can reach the log. A
disabled plugin and a plugin without ``register_requirements`` must not stop startup.
"""

import dataclasses
import importlib.metadata
import sys
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from structlog.testing import capture_logs

from contracts.plugins.namespace import PLUGIN_NAMESPACE
from contracts.plugins.requirements import RequiredDependencyError
from server.configuration import load_host_configuration
from server.lifespan import build_lifespan
from server.plugins.manager import get_plugin_manager
from tests.fixtures.plugin_dists import write_plugin_dist

pytestmark = pytest.mark.integration

NEEDY_MODULE = "fake_plugin_needing_openai"
NEEDY_SOURCE = """
from contracts.plugins.namespace import hookimpl
from contracts.plugins.requirements import RequiredDependencyError


@hookimpl
def register_requirements():
    raise RequiredDependencyError("openai.tenant")
"""
WARMUP_MODULE = "fake_plugin_invalid_settings"
WARMUP_SOURCE = """
from pydantic import BaseModel

from contracts.plugins.namespace import hookimpl


class FakeSettings(BaseModel):
    channel_id: int


@hookimpl
def startup_warmup(logger):
    FakeSettings.model_validate({"channel_id": "not-a-number"})
"""
PLAIN_MODULE = "fake_plugin_without_requirements"
PLAIN_SOURCE = """
from contracts.plugins.namespace import hookimpl


@hookimpl
def startup_warmup(logger):
    logger.info("fake_plugin_warmed_up")
"""
EVENT_FIELDS = {"event", "log_level", "plugin", "phase", "error_type", "setting"}


@pytest.fixture(autouse=True)
def _fresh_plugin_manager() -> Iterator[None]:
    get_plugin_manager.cache_clear()
    yield
    get_plugin_manager.cache_clear()
    for module in (NEEDY_MODULE, WARMUP_MODULE, PLAIN_MODULE):
        sys.modules.pop(module, None)


def _install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, entry_points: dict[str, str], modules: dict[str, str]) -> None:
    dist = write_plugin_dist(tmp_path, PLUGIN_NAMESPACE, entry_points, modules)
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


def _boot_failures(events: list[dict[str, object]]) -> list[dict[str, object]]:
    return [event for event in events if event["event"] == "plugin_boot_failed"]


async def test_lifespan_aborts_naming_the_plugin_and_setting_when_a_required_dependency_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configuration = load_host_configuration()
    _install(monkeypatch, tmp_path, {"needy": NEEDY_MODULE}, {NEEDY_MODULE: NEEDY_SOURCE})
    reached_yield = False

    with ExitStack() as stack, capture_logs() as events, pytest.raises(RequiredDependencyError):
        _stub_startup(stack)
        async with build_lifespan(configuration)(FastAPI()):
            reached_yield = True

    assert reached_yield is False
    (event,) = _boot_failures(events)
    assert set(event) == EVENT_FIELDS
    assert event["log_level"] == "critical"
    assert (event["plugin"], event["phase"], event["error_type"], event["setting"]) == (
        "needy",
        "register_requirements",
        "RequiredDependencyError",
        "openai.tenant",
    )


async def test_lifespan_aborts_naming_the_setting_when_a_plugin_settings_slice_fails_validation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configuration = load_host_configuration()
    _install(monkeypatch, tmp_path, {"invalid": WARMUP_MODULE}, {WARMUP_MODULE: WARMUP_SOURCE})
    reached_yield = False

    with ExitStack() as stack, capture_logs() as events, pytest.raises(ValidationError):
        _stub_startup(stack)
        async with build_lifespan(configuration)(FastAPI()):
            reached_yield = True

    assert reached_yield is False
    (event,) = _boot_failures(events)
    assert set(event) == EVENT_FIELDS
    assert (event["plugin"], event["phase"], event["setting"]) == ("invalid", "startup_warmup", "FakeSettings.channel_id")
    assert "not-a-number" not in repr(events)


async def test_lifespan_attributes_an_import_failure_to_its_entry_point(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configuration = load_host_configuration()
    _install(monkeypatch, tmp_path, {"broken": "fake_plugin_module_that_does_not_exist"}, {})

    with ExitStack() as stack, capture_logs() as events, pytest.raises(ModuleNotFoundError):
        _stub_startup(stack)
        async with build_lifespan(configuration)(FastAPI()):
            pass

    (event,) = _boot_failures(events)
    assert (event["plugin"], event["phase"], event["error_type"], event["setting"]) == (
        "broken",
        "plugin_loading",
        "ModuleNotFoundError",
        None,
    )


async def test_lifespan_boots_when_the_plugin_whose_requirement_fails_is_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configuration = dataclasses.replace(load_host_configuration(), disabled_plugins=frozenset({"needy"}))
    _install(monkeypatch, tmp_path, {"needy": NEEDY_MODULE}, {NEEDY_MODULE: NEEDY_SOURCE})

    with ExitStack() as stack, capture_logs() as events:
        _stub_startup(stack)
        async with build_lifespan(configuration)(FastAPI()):
            pass

    assert _boot_failures(events) == []
    assert NEEDY_MODULE not in sys.modules


async def test_lifespan_boots_a_plugin_that_states_no_requirements(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configuration = load_host_configuration()
    _install(monkeypatch, tmp_path, {"plain": PLAIN_MODULE}, {PLAIN_MODULE: PLAIN_SOURCE})

    with ExitStack() as stack, capture_logs() as events:
        _stub_startup(stack)
        async with build_lifespan(configuration)(FastAPI()):
            pass

    assert _boot_failures(events) == []
    assert "fake_plugin_warmed_up" in [event["event"] for event in events]
