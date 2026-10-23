"""Unit tests for /secret command registration.

Verifies that secret.register() builds the Bolt slash-command name from
the installed SlackTransportInfo's command_prefix for both the empty-prefix
(production) and 'dev-' (dev) cases.

secret.register() also calls bot.action('secret_change_locale') and
bot.view('secret_view'); bot is a MagicMock so those calls are inert and
do not interfere with the bot.command assertion.
"""

from unittest.mock import MagicMock

import pytest

from contracts.slack.transport import SlackTransportInfo, install_slack_transport_info
from modules.secret import secret


@pytest.mark.unit
@pytest.mark.parametrize(
    "command_prefix, expected_command",
    [
        ("", "/secret"),
        ("dev-", "/dev-secret"),
    ],
    ids=[
        "empty-prefix-registers-slash-secret",
        "dev-prefix-registers-slash-dev-secret",
    ],
)
def test_secret_register_builds_command_name_from_command_prefix(command_prefix: str, expected_command: str) -> None:
    """register() builds the Bolt slash-command by prepending COMMAND_PREFIX to 'secret'.

    Installs the SlackTransportInfo contract so the test is isolated from the
    environment. Asserts bot.command is called exactly once with the full
    slash-command string. The bot.action() and bot.view() calls in register()
    are inert on a MagicMock and do not affect the bot.command assertion.
    """
    install_slack_transport_info(SlackTransportInfo(command_prefix=command_prefix))
    bot = MagicMock()

    secret.register(bot)

    bot.command.assert_called_once_with(expected_command)
