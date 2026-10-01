"""Integration tests for the single /sre Slack command registration at startup."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from infrastructure.slack.settings import get_slack_transport_settings
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from modules.dev import register_slack_commands as register_dev_commands
from modules.sre import register_slack_commands as register_sre_commands
from server.lifespan import _register_legacy_handlers


@pytest.mark.integration
def test_register_legacy_handlers_and_hookimpl_path_register_sre_command_once(mock_bot):
    """The /sre slash command is registered on the Bolt app exactly once.

    Runs both startup registration phases against one recording bot: the
    real sre and dev register_slack_commands hookimpls followed by the
    provider's root-command auto-registration, then the hard-coded legacy
    handler list. Only the modules that could register /sre run for real; the
    other legacy modules are patched out because they register unrelated
    commands and interactions. Both phases build the slash command from the
    same transport prefix, so a count above one means the command is wired by
    two paths.
    """
    # Arrange
    command_prefix = get_slack_transport_settings().COMMAND_PREFIX
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    provider = SlackPlatformProvider(
        settings=settings,
        formatter=SlackBlockKitFormatter(),
        command_prefix=command_prefix,
    )
    provider._app = mock_bot

    # Act
    register_sre_commands(registrar=provider)
    register_dev_commands(registrar=provider)
    provider._auto_register_root_commands()
    with (
        patch("server.lifespan.role"),
        patch("server.lifespan.atip"),
        patch("server.lifespan.aws"),
        patch("server.lifespan.secret"),
        patch("server.lifespan.webhook_helper"),
        patch("server.lifespan.incident"),
        patch("server.lifespan.incident_helper"),
    ):
        _register_legacy_handlers(mock_bot, MagicMock())

    # Assert
    registered = [call.args[0] for call in mock_bot.command.call_args_list]
    assert registered.count(f"/{command_prefix}sre") == 1
