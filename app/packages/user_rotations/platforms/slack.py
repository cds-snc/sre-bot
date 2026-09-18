"""Slack command interface for viewing user rotations."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from integrations.slack.models import Argument, ArgumentType, CommandPayload, CommandResponse
from packages.user_rotations.providers import get_user_rotations_service
from packages.user_rotations.service import UserRotationShift, UserRotationsService

if TYPE_CHECKING:
    from slack_sdk import WebClient

    from integrations.slack.provider import SlackPlatformProvider

README_URL = "https://github.com/cds-snc/sre-bot/blob/main/app/packages/user_rotations/README.md"


def register_commands(provider: SlackPlatformProvider) -> None:
    """Register ``/sre rotations`` commands."""

    def dispatch(payload: CommandPayload, parsed_args: dict[str, Any]) -> CommandResponse:
        return handle_view_command(payload, parsed_args, provider.client, get_user_rotations_service())

    provider.register_command(
        command="rotations",
        handler=handle_rotations_help,
        parent="sre",
        description="View self-managed user rotations",
    )
    provider.register_command(
        command="view",
        handler=dispatch,
        parent="sre.rotations",
        description="View a user rotation",
        usage_hint="<usergroup-handle>",
        arguments=[
            Argument(
                name="usergroup_handle",
                type=ArgumentType.STRING,
                required=True,
                description="Slack UserGroup handle",
            )
        ],
    )


def handle_rotations_help(_: CommandPayload) -> CommandResponse:
    """Return the user-rotations command list."""
    return CommandResponse(
        message=(
            "Manage user rotations. This is a light-weight alternative to OpsGenie for non-critical usecases. "
            f"Learn more <{README_URL}|here>.\n\n"
            "*Commands:*\n\n"
            "`/sre rotations help` - View this help page.\n"
            "`/sre rotations view <usergroup-handle>` - View shifts for a rotation."
        ),
        ephemeral=True,
    )


def handle_view_command(
    payload: CommandPayload,
    parsed_args: dict[str, Any],
    client: WebClient | None,
    service: UserRotationsService,
) -> CommandResponse:
    """Open a modal showing the selected rotation's next 12 weeks of shifts."""
    handle = str(parsed_args["usergroup_handle"])
    shifts = service.get_rotation_shifts(handle)
    if shifts is None:
        return CommandResponse(message=f"No user rotation configured for `{handle}`.", ephemeral=True)

    trigger_id = str(payload.platform_metadata.get("trigger_id", ""))
    if client is None or not trigger_id:
        return CommandResponse(message="Unable to open the user rotation view.", ephemeral=True)

    client.views_open(trigger_id=trigger_id, view=_modal(shifts))
    return CommandResponse(message="", ephemeral=True)


def _modal(shifts: list[UserRotationShift]) -> dict[str, Any]:
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": "User rotation"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(_format_shift(shift) for shift in shifts)}}],
    }


def _format_shift(shift: UserRotationShift) -> str:
    return f"<@{shift.slack_user_id}> | {_format_datetime(shift.start)} - {_format_datetime(shift.end)}"


def _format_datetime(value: datetime) -> str:
    fallback = value.strftime("%Y-%m-%d %H:%M %Z")
    return f"<!date^{int(value.timestamp())}^{{date_short}} {{time}}|{fallback}>"
