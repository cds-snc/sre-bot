"""Behavior tests for ATIP slash-command registration.

Stubs both transport settings and app settings so command-name composition is
deterministic and isolated from process environment.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from modules import atip


@pytest.mark.unit
@pytest.mark.parametrize(
    "command_prefix,legacy_prefix,expected_commands",
    [
        ("", "legacy-", {"/atip", "/aiprp"}),
        ("dev-", "", {"/dev-atip", "/dev-aiprp"}),
    ],
    ids=[
        "empty-command-prefix-registers-unprefixed-atip-commands",
        "dev-command-prefix-registers-dev-prefixed-atip-commands",
    ],
)
def test_register_builds_atip_command_names_from_command_prefix(
    command_prefix: str,
    legacy_prefix: str,
    expected_commands: set[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """register() should compose /atip and /aiprp from COMMAND_PREFIX only."""
    monkeypatch.setattr(
        atip,
        "get_slack_transport_settings",
        lambda: SimpleNamespace(COMMAND_PREFIX=command_prefix),
        raising=False,
    )
    monkeypatch.setattr(
        atip,
        "get_app_settings",
        lambda: SimpleNamespace(PREFIX=legacy_prefix, ENVIRONMENT="dev"),
    )

    bot = MagicMock()

    atip.register(bot)

    actual_commands = {call.args[0] for call in bot.command.call_args_list}
    assert bot.command.call_count == 2
    assert actual_commands == expected_commands
