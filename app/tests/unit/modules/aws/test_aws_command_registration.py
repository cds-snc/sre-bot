"""Unit tests for /aws command registration.

Verifies that aws.register() builds the Bolt slash-command name from
get_slack_transport_settings().COMMAND_PREFIX for both the empty-prefix
(production) and 'dev-' (dev) cases, and that it registers exactly one
Bolt view handler, aws_health_view.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modules.aws import aws


@pytest.mark.unit
@pytest.mark.parametrize(
    "command_prefix, expected_command",
    [
        ("", "/aws"),
        ("dev-", "/dev-aws"),
    ],
    ids=["empty-prefix-registers-slash-aws", "dev-prefix-registers-slash-dev-aws"],
)
def test_aws_register_builds_command_name_from_command_prefix(
    command_prefix: str, expected_command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """register() builds the Bolt slash-command by prepending COMMAND_PREFIX to 'aws'.

    Stubs get_slack_transport_settings() so the test is isolated from the
    environment. bot is a MagicMock, so the registration calls are recorded
    and nothing is actually wired. Asserts bot.command is called exactly once
    with the full slash-command string, and bot.view exactly once with
    aws_health_view.
    """
    monkeypatch.setattr(
        aws,
        "get_slack_transport_settings",
        lambda: SimpleNamespace(COMMAND_PREFIX=command_prefix),
    )
    bot = MagicMock()

    aws.register(bot)

    bot.command.assert_called_once_with(expected_command)
    bot.view.assert_called_once_with("aws_health_view")
