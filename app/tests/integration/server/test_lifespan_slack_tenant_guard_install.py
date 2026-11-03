"""Integration test for the Slack tenant guard install during the lifespan.

Every startup service is stubbed and the provider holds a mock Bolt app. The
guard install and the legacy handler registration are recorded on one parent
mock, so the test observes that the guard is installed on the provider's app,
with the configured tenant entry, as the first step after the app is available.
Bolt runs a global middleware ahead of every listener whatever their
registration order, so the position pins the wiring, not the behaviour.
"""

from collections.abc import Iterator
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi import FastAPI

from integrations.slack.settings import SlackTenant
from tests.factories.lifespan import lifespan

TENANT = SlackTenant(team_id="T0TEAM")


@pytest.fixture
def provider() -> MagicMock:
    provider = MagicMock()
    provider.app = MagicMock(name="bolt_app")
    provider.start.return_value.is_success = True
    return provider


@pytest.fixture
def recorder(provider: MagicMock) -> Iterator[MagicMock]:
    recorder = MagicMock()
    with ExitStack() as stack:
        stack.enter_context(patch("server.lifespan._get_logger_from_app", return_value=MagicMock()))
        stack.enter_context(patch("server.lifespan.initialize_core_services"))
        stack.enter_context(patch("server.lifespan._initialize_security_services"))
        stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
        stack.enter_context(patch("server.lifespan.get_plugin_manager"))
        stack.enter_context(patch("server.lifespan.load_plugins"))
        stack.enter_context(patch("server.lifespan._initialize_translation_service"))
        stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
        stack.enter_context(patch("server.lifespan.register_feature_integrations"))
        stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))
        stack.enter_context(patch("server.lifespan.get_slack_settings", return_value=SimpleNamespace(tenant=TENANT)))
        stack.enter_context(patch("server.lifespan.install_slack_tenant_guard", recorder.install))
        stack.enter_context(patch("server.lifespan._register_legacy_handlers", recorder.register_legacy))
        yield recorder


@pytest.mark.integration
async def test_lifespan_installs_the_tenant_guard_on_the_slack_app(recorder: MagicMock, provider: MagicMock) -> None:
    """The lifespan installs the guard on the provider's Bolt app with the configured tenant entry."""
    async with lifespan(FastAPI()):
        pass

    assert recorder.mock_calls[:2] == [
        call.install(provider.app, TENANT),
        call.register_legacy(provider.app, recorder.register_legacy.call_args.args[1]),
    ]
