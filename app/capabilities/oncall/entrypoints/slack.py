"""Slack entry points of the on-call capability: ``/sre rotations`` over the self-managed rotations.

The one case where a capability has entry points (decisions/oncall.md). Each handler makes one
lookup call; the sync Bolt edge bridges it with one ``asyncio.run``.
"""

import asyncio
from datetime import datetime
from typing import Any

import structlog

from capabilities.oncall.api import ROTATIONS, OnCallLookup, OnCallPerson, ScheduleReference, Shift, get_oncall_lookup
from contracts.operations.status import OperationStatus
from contracts.slack.models import Argument, ArgumentType, CommandPayload, CommandResponse
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplySender

logger = structlog.get_logger()

README_URL = "https://github.com/cds-snc/sre-bot/blob/main/app/capabilities/oncall/README.md"
SLACK_PLATFORM = "slack"


def register_commands(registrar: SlackCommandRegistrar) -> None:
    """Register ``/sre rotations`` commands."""

    def dispatch(payload: CommandPayload, parsed_args: dict[str, Any]) -> CommandResponse:
        return handle_view_command(payload, parsed_args, registrar.reply, get_oncall_lookup())

    registrar.register_command(
        command="rotations",
        handler=handle_rotations_help,
        parent="sre",
        description="View self-managed user rotations",
    )
    registrar.register_command(
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
    reply: SlackReplySender,
    lookup: OnCallLookup,
) -> CommandResponse:
    """Open a modal showing the selected rotation's active shift and those of the next 12 weeks."""
    handle = str(parsed_args["usergroup_handle"])
    result = asyncio.run(lookup.get_schedule(ScheduleReference(ROTATIONS, handle)))
    if result.status is OperationStatus.NOT_FOUND:
        return CommandResponse(message=f"No user rotation configured for `{handle}`.", ephemeral=True)
    if not result.is_success or result.data is None:
        logger.warning(
            "user_rotations_view_lookup_failed", usergroup_handle=handle, error=result.message, error_code=result.error_code
        )
        return CommandResponse(message="Unable to open the user rotation view.", ephemeral=True)

    trigger_id = str(payload.platform_metadata.get("trigger_id", ""))
    if not trigger_id:
        return CommandResponse(message="Unable to open the user rotation view.", ephemeral=True)

    opened = reply.open_view(trigger_id=trigger_id, view=_modal(result.data.shifts))
    if not opened.is_success:
        logger.warning(
            "user_rotations_view_open_failed",
            usergroup_handle=handle,
            error=opened.message,
            error_code=opened.error_code,
        )
        return CommandResponse(message="Unable to open the user rotation view.", ephemeral=True)
    return CommandResponse(message="", ephemeral=True)


def _modal(shifts: tuple[Shift, ...]) -> dict[str, Any]:
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": "User rotation"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(_format_shift(shift) for shift in shifts)}}],
    }


def _format_shift(shift: Shift) -> str:
    return f"{_mention(shift.person)} | {_format_datetime(shift.start)} - {_format_datetime(shift.end)}"


def _mention(person: OnCallPerson) -> str:
    if person.account is not None and person.account.platform == SLACK_PLATFORM:
        return f"<@{person.account.account_id}>"
    return person.email or "unknown"


def _format_datetime(value: datetime) -> str:
    fallback = value.strftime("%Y-%m-%d %H:%M %Z")
    return f"<!date^{int(value.timestamp())}^{{date_short}} {{time}}|{fallback}>"
