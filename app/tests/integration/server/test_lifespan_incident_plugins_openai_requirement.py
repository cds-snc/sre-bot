"""Integration tests for the incident plugins' OpenAI requirement at boot, on the real entry points.

The real lifespan loads the installed plugins on a freshly built plugin manager;
core services, security, the directory, the Slack provider, translation and feature
registration are stubbed, since requirements are resolved before any of them. The
ci files configure no tenant. With incident.scribe enabled (the
configuration's disabled set replaced by the access plugins and the other plugins that declare requirements) startup must stop
before the lifespan yields, naming each tenant scribe declares: it has no fallback. With the ci
files as they are (scribe off, comms on) startup must reach the yield and comms must
report text generation unavailable, its designed fallback.
"""

import dataclasses
from collections.abc import Iterator
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from structlog.testing import capture_logs

from features.incident.comms.providers import get_status_update_text_generator, text_generation_available
from integrations.openai import get_openai_settings
from server.configuration import load_host_configuration
from server.lifespan import build_lifespan
from server.plugins.manager import get_plugin_manager
from server.plugins.requirements import PluginRequirementsUnmetError

pytestmark = pytest.mark.integration

ACCESS_PLUGINS = frozenset({"access.catalog", "access.request", "access.sync"})
OTHER_REQUIRING_PLUGINS = frozenset({"oncall_sync", "user_rotations", "rant"})


@pytest.fixture(autouse=True)
def _fresh_plugin_manager() -> Iterator[None]:
    get_plugin_manager.cache_clear()
    get_openai_settings.cache_clear()
    get_status_update_text_generator.cache_clear()
    yield
    get_plugin_manager.cache_clear()
    get_openai_settings.cache_clear()
    get_status_update_text_generator.cache_clear()


def _stub_startup(stack: ExitStack) -> None:
    provider = MagicMock()
    provider.app = None
    stack.enter_context(patch("server.lifespan.initialize_core_services"))
    stack.enter_context(patch("server.lifespan._initialize_security_services"))
    stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
    stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
    stack.enter_context(patch("server.lifespan._initialize_translation_service"))
    stack.enter_context(patch("server.lifespan.register_feature_integrations"))
    stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))


async def test_lifespan_aborts_naming_every_tenant_scribe_lacks_when_it_is_enabled() -> None:
    configuration = dataclasses.replace(load_host_configuration(), disabled_plugins=ACCESS_PLUGINS | OTHER_REQUIRING_PLUGINS)
    reached_yield = False

    with ExitStack() as stack, capture_logs() as events, pytest.raises(PluginRequirementsUnmetError):
        _stub_startup(stack)
        async with build_lifespan(configuration)(FastAPI()):
            reached_yield = True

    assert reached_yield is False
    failures = [event for event in events if event["event"] == "plugin_boot_failed"]
    assert [(event["plugin"], event["setting"]) for event in failures] == [
        ("incident.scribe", "openai.tenant"),
        ("incident.scribe", "slack.tenant"),
        ("incident.scribe", "google_workspace.tenant"),
    ]


async def test_lifespan_boots_with_comms_reporting_text_generation_unavailable_when_scribe_is_off() -> None:
    configuration = load_host_configuration()

    with ExitStack() as stack:
        _stub_startup(stack)
        async with build_lifespan(configuration)(FastAPI()):
            registered = {get_plugin_manager().get_name(plugin) for plugin, _ in get_plugin_manager().list_plugin_distinfo()}
            available = text_generation_available()

    assert "incident.scribe" in configuration.disabled_plugins
    assert "incident.comms" in registered
    assert available is False
