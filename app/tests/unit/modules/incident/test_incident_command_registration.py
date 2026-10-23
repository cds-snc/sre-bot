"""Unit tests for /incident command registration.

Verifies that incident.register() builds the Bolt slash-command name from
the installed SlackTransportInfo's command_prefix for both the empty-prefix
(production) and 'dev-' (dev) cases.
"""

from unittest.mock import MagicMock

import pytest

from contracts.slack.transport import SlackTransportInfo, install_slack_transport_info
from modules.incident import incident


@pytest.mark.unit
@pytest.mark.parametrize(
    "command_prefix, expected_command",
    [
        ("", "/incident"),
        ("dev-", "/dev-incident"),
    ],
    ids=[
        "empty-prefix-registers-slash-incident",
        "dev-prefix-registers-slash-dev-incident",
    ],
)
def test_incident_register_builds_command_name_from_command_prefix(command_prefix: str, expected_command: str) -> None:
    """register() prepends COMMAND_PREFIX to the base incident command name.

    Installs the SlackTransportInfo contract so the test is isolated from the
    environment. Asserts bot.command is called once with the full
    slash-command string.
    """
    install_slack_transport_info(SlackTransportInfo(command_prefix=command_prefix))
    bot = MagicMock()

    incident.register(bot)

    bot.command.assert_called_once_with(expected_command)
