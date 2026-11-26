"""Integration tests for the extension-point phase inside the real lifespan.

The lifespan runs on a freshly built plugin manager whose entry points come from a
throwaway dist-info (``tests.fixtures.plugin_dists``): a test capability, importable as
``capabilities.fake_lifespan_capability`` through a temporary directory added to the
``capabilities`` package path, and a test feature that contributes to it and registers a
route. Core services, security, the directory, the Slack provider and translation are
stubbed; translation records when it ran. Each hook appends to a shared list, so the
assertions read the phase order a plugin author relies on: translation, then the
extension point, then feature registration, and an initialize that raises stops startup
before the lifespan yields with one ``plugin_boot_failed`` naming the capability.
"""

import importlib.metadata
import sys
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from structlog.testing import capture_logs

import capabilities
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from server.configuration import load_host_configuration
from server.lifespan import build_lifespan
from server.plugins.manager import get_plugin_manager
from tests.fixtures.plugin_dists import write_plugin_dist

pytestmark = pytest.mark.integration

CAPABILITY = "fake_lifespan_capability"
CAPABILITY_MODULE = f"capabilities.{CAPABILITY}"
FEATURE_MODULE = "fake_lifespan_feature"
CAPABILITY_SOURCE = """
from contracts.plugins.extension_points import ExtensionPoint
from contracts.plugins.namespace import hookimpl, hookspec

CALLS = []
FAIL = []


class FakeSpecs:
    @hookspec
    def register_fake_strategies(self):
        \"\"\"Return the strategies a plugin contributes.\"\"\"


class FakeValue:
    def __init__(self, strategies):
        self.strategies = strategies


def initialize(context):
    if FAIL:
        raise RuntimeError("refused")
    CALLS.append(("extension_point", dict(context.collect("register_fake_strategies"))))
    return FakeValue(CALLS[-1][1])


@hookimpl
def register_extension_points(registrar):
    registrar.declare(ExtensionPoint(specs=FakeSpecs, provides=FakeValue, initialize=initialize))
"""
FEATURE_SOURCE = f"""
from contracts.plugins.namespace import hookimpl

from {CAPABILITY_MODULE} import CALLS


@hookimpl
def register_fake_strategies():
    return ["strategy"]


@hookimpl
def register_routes(app):
    CALLS.append(("feature_registration", None))
"""


@pytest.fixture(autouse=True)
def _fresh_plugin_manager() -> Iterator[None]:
    get_plugin_manager.cache_clear()
    yield
    get_plugin_manager.cache_clear()
    for module in (CAPABILITY_MODULE, FEATURE_MODULE):
        sys.modules.pop(module, None)


def _install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    package_dir = tmp_path / "capability_package"
    package_dir.mkdir()
    (package_dir / f"{CAPABILITY}.py").write_text(CAPABILITY_SOURCE)
    monkeypatch.setattr(capabilities, "__path__", [*capabilities.__path__, str(package_dir)])
    dist = write_plugin_dist(
        tmp_path,
        PLUGIN_NAMESPACE,
        {CAPABILITY: CAPABILITY_MODULE, "fake_feature": FEATURE_MODULE},
        {FEATURE_MODULE: FEATURE_SOURCE},
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(importlib.metadata, "distributions", lambda: [dist])


def _stub_startup(stack: ExitStack, calls: list[tuple[str, object]]) -> None:
    provider = MagicMock()
    provider.app = None
    stack.enter_context(patch("server.lifespan.initialize_core_services"))
    stack.enter_context(patch("server.lifespan._initialize_security_services"))
    stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
    stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))

    def translation(*_: object) -> MagicMock:
        calls.append(("i18n", None))
        return MagicMock()

    stack.enter_context(patch("server.lifespan._initialize_translation_service", side_effect=translation))
    stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))


async def test_the_extension_point_initializes_after_i18n_and_before_feature_registration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The capability collects the feature's strategy once, between translation and feature registration."""
    configuration = load_host_configuration()
    _install(monkeypatch, tmp_path)
    calls: list[tuple[str, object]] = []
    import capabilities.fake_lifespan_capability as capability  # noqa: PLC0415 - exists only once installed

    monkeypatch.setattr(capability, "CALLS", calls)

    with ExitStack() as stack:
        _stub_startup(stack, calls)
        async with build_lifespan(configuration)(FastAPI()):
            pass

    assert calls == [
        ("i18n", None),
        ("extension_point", {"fake_feature": ["strategy"]}),
        ("feature_registration", None),
    ]


async def test_a_raising_initialize_stops_startup_before_yield_naming_the_capability(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A capability that refuses its collection aborts boot before any feature registers."""
    configuration = load_host_configuration()
    _install(monkeypatch, tmp_path)
    calls: list[tuple[str, object]] = []
    import capabilities.fake_lifespan_capability as capability  # noqa: PLC0415 - exists only once installed

    monkeypatch.setattr(capability, "CALLS", calls)
    monkeypatch.setattr(capability, "FAIL", [True])
    reached_yield = False

    with ExitStack() as stack, capture_logs() as events, pytest.raises(RuntimeError, match="refused"):
        _stub_startup(stack, calls)
        async with build_lifespan(configuration)(FastAPI()):
            reached_yield = True

    assert reached_yield is False
    assert ("feature_registration", None) not in calls
    failures = [(e["plugin"], e["phase"]) for e in events if e["event"] == "plugin_boot_failed"]
    assert failures == [(CAPABILITY, "extension_points")]
