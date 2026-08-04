"""Unit tests for /sre command registration.

Verifies that sre.register() builds the Bolt slash-command name from
get_slack_transport_settings().COMMAND_PREFIX for both the empty-prefix
(production) and 'dev-' (dev) cases.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modules.sre import sre


@pytest.mark.unit
@pytest.mark.parametrize(
    "command_prefix, expected_command",
    [
        ("", "/sre"),
        ("dev-", "/dev-sre"),
    ],
    ids=["empty-prefix-registers-slash-sre", "dev-prefix-registers-slash-dev-sre"],
)
def test_sre_register_builds_command_name_from_command_prefix(
    command_prefix: str, expected_command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """register() builds the Bolt slash-command by prepending COMMAND_PREFIX to 'sre'.

    Stubs get_slack_transport_settings() so the test is isolated from the
    environment. Asserts bot.command is called exactly once with the full
    slash-command string.
    """
    monkeypatch.setattr(
        sre,
        "get_slack_transport_settings",
        lambda: SimpleNamespace(COMMAND_PREFIX=command_prefix),
    )
    bot = MagicMock()

    sre.register(bot)

    bot.command.assert_called_once_with(expected_command)
