"""Unit tests for /talent-role command registration.

Verifies that role.register() builds the Bolt slash-command name from
get_slack_transport_settings().COMMAND_PREFIX for both the empty-prefix
(production) and 'dev-' (dev) cases.

role.register() also calls bot.view('role_view') and
bot.action('role_change_locale'); bot is a MagicMock so those calls are
inert and do not interfere with the bot.command assertion.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modules.role import role


@pytest.mark.unit
@pytest.mark.parametrize(
    "command_prefix, expected_command",
    [
        ("", "/talent-role"),
        ("dev-", "/dev-talent-role"),
    ],
    ids=[
        "empty-prefix-registers-slash-talent-role",
        "dev-prefix-registers-slash-dev-talent-role",
    ],
)
def test_role_register_builds_command_name_from_command_prefix(
    command_prefix: str, expected_command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """register() builds the Bolt slash-command by prepending COMMAND_PREFIX to 'talent-role'.

    Stubs get_slack_transport_settings() so the test is isolated from the
    environment. Asserts bot.command is called exactly once with the full
    slash-command string. The bot.view() and bot.action() calls in register()
    are inert on a MagicMock and do not affect the bot.command assertion.
    """
    monkeypatch.setattr(
        role,
        "get_slack_transport_settings",
        lambda: SimpleNamespace(COMMAND_PREFIX=command_prefix),
    )
    bot = MagicMock()

    role.register(bot)

    bot.command.assert_called_once_with(expected_command)
