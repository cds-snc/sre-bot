"""Unit tests for the user-rotations Slack interface."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from integrations.slack.models import CommandPayload
from packages.user_rotations.platforms.slack import (
    handle_rotations_help,
    handle_view_command,
    register_commands,
)
from packages.user_rotations.service import UserRotationShift

pytestmark = pytest.mark.unit


def test_register_commands_adds_rotations_help_and_view_under_sre() -> None:
    provider = MagicMock()

    register_commands(provider)

    parent, view = [call.kwargs for call in provider.register_command.call_args_list]
    assert parent["command"] == "rotations"
    assert parent["parent"] == "sre"
    assert parent["handler"] is handle_rotations_help
    assert view["command"] == "view"
    assert view["parent"] == "sre.rotations"
    assert view["usage_hint"] == "<usergroup-handle>"


def test_rotations_help_lists_the_view_command_and_readme() -> None:
    response = handle_rotations_help(CommandPayload(text="", user_id="U1"))

    assert response.ephemeral is True
    assert "Manage user rotations" in response.message


def test_view_command_opens_modal_with_one_line_per_shift() -> None:
    client = MagicMock()
    payload = CommandPayload(text="", user_id="U1", platform_metadata={"trigger_id": "trigger"})
    shifts = [
        UserRotationShift("U1", datetime(2026, 9, 14, 9, tzinfo=UTC), datetime(2026, 9, 21, 9, tzinfo=UTC)),
        UserRotationShift("U2", datetime(2026, 9, 21, 9, tzinfo=UTC), datetime(2026, 9, 28, 9, tzinfo=UTC)),
    ]
    service = MagicMock()
    service.get_rotation_shifts.return_value = shifts

    response = handle_view_command(payload, {"usergroup_handle": "fielding-questions"}, client, service)

    assert response.message == ""
    assert response.ephemeral is True
    client.views_open.assert_called_once()
    kwargs = client.views_open.call_args.kwargs
    assert kwargs["trigger_id"] == "trigger"
    text = kwargs["view"]["blocks"][0]["text"]["text"]
    assert text.splitlines() == [
        "<@U1> | <!date^1789376400^{date_short} {time}|2026-09-14 09:00 UTC> - <!date^1789981200^{date_short} {time}|2026-09-21 09:00 UTC>",
        "<@U2> | <!date^1789981200^{date_short} {time}|2026-09-21 09:00 UTC> - <!date^1790586000^{date_short} {time}|2026-09-28 09:00 UTC>",
    ]
