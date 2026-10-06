"""Integration tests for where the lifespan registers the legacy sre and dev Slack commands."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from server.lifespan import _register_legacy_slack_commands, lifespan


@pytest.mark.integration
def test_register_legacy_slack_commands_registers_sre_then_dev_on_the_registrar() -> None:
    """The helper hands the same registrar to the sre module, then to the dev module."""
    registrar = MagicMock()

    with patch("server.lifespan.sre") as sre, patch("server.lifespan.dev") as dev:
        sre.register_commands.side_effect = lambda registrar: registrar.mark("sre")
        dev.register_commands.side_effect = lambda registrar: registrar.mark("dev")

        _register_legacy_slack_commands(registrar, MagicMock())

    assert [call.args[0] for call in registrar.mark.call_args_list] == ["sre", "dev"]


@pytest.mark.integration
async def test_lifespan_registers_legacy_slack_commands_before_the_slack_app_is_built() -> None:
    """Legacy sre and dev commands reach the provider before initialize_app binds root commands.

    Startup services are stubbed so only the registration order is observed:
    one parent mock records the feature hook call, the legacy registration
    and the provider's initialize_app in the order they happen. The provider
    exposes no Bolt app, so startup skips the legacy Bolt handlers and the
    scheduled jobs.
    """
    calls = MagicMock()
    provider = calls.provider
    provider.app = None

    with (
        patch("server.lifespan._initialize_security_services"),
        patch("server.lifespan._initialize_directory_provider"),
        patch("server.lifespan._initialize_translation_service"),
        patch("server.lifespan.get_plugin_manager"),
        patch("server.lifespan.load_plugins"),
        patch("server.lifespan.get_slack_provider", return_value=provider),
        patch("server.lifespan.register_feature_integrations", calls.register_feature_integrations),
        patch("server.lifespan._register_legacy_slack_commands", calls.register_legacy_slack_commands),
    ):
        async with lifespan(FastAPI()):
            pass

    order = [name for name, *_ in calls.mock_calls]
    startup = [
        name
        for name in order
        if name in {"register_feature_integrations", "register_legacy_slack_commands", "provider.initialize_app"}
    ]
    assert startup == ["register_feature_integrations", "register_legacy_slack_commands", "provider.initialize_app"]
    assert calls.register_legacy_slack_commands.call_args.args[0] is provider
