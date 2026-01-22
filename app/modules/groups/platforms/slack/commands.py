"""Slack platform commands for Groups module.

Registers groups-related commands (list, add, remove) using the
platform providers framework with argument parsing and schema validation.

Step 1: migrate "list" subcommand.
"""

import structlog
from typing import TYPE_CHECKING, Any, Dict, Optional

from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.platforms.parsing import Argument, ArgumentType
from modules.groups.api import schemas
from modules.groups.core import service

if TYPE_CHECKING:
    from infrastructure.platforms.providers.slack import SlackPlatformProvider

logger = structlog.get_logger()


# ---- Argument definitions for `sre groups list` ----
_GROUPS_LIST_ARGUMENTS = [
    # Provider filter
    Argument(
        name="--provider",
        type=ArgumentType.CHOICE,
        choices=[
            "google",
            "okta",
            "azure",
            "aws",
            "slack",
        ],
        description="Filter by provider",
    ),
    # Include group members in the response
    Argument(
        name="--include-members",
        type=ArgumentType.BOOLEAN,
        description="Include group members",
    ),
    # Enrich members with user details (requires include-members)
    Argument(
        name="--include-users-details",
        type=ArgumentType.BOOLEAN,
        description="Enrich members with user details",
    ),
    # Filter by member roles (allow multiple)
    Argument(
        name="--role",
        type=ArgumentType.CHOICE,
        choices=["OWNER", "MANAGER", "MEMBER"],
        allow_multiple=True,
        description="Filter by member role",
        aliases=["-r"],
    ),
    # Include empty groups (maps to exclude_empty_groups=False)
    Argument(
        name="--include-empty",
        type=ArgumentType.BOOLEAN,
        description="Include empty groups",
    ),
    # Target user (whose groups to list)
    Argument(
        name="--user",
        type=ArgumentType.EMAIL,
        description="Target user email",
        aliases=["-u"],
    ),
]


def _map_list_arguments(
    parsed: Dict[str, Any], payload: CommandPayload
) -> Dict[str, Any]:
    """Map parsed arguments to ListGroupsRequest fields.

    Adds required fields like requestor from payload, translates flags
    to schema booleans, and normalizes role filters.
    """
    requestor_email: Optional[str] = payload.user_email or None
    # Fallback to platform metadata if available
    if not requestor_email and payload.platform_metadata:
        requestor_email = payload.platform_metadata.get("user_email")

    # Build payload for schema
    mapped: Dict[str, Any] = {
        "requestor": requestor_email or "requestor@example.com",
        "provider": parsed.get("--provider"),
        "include_members": bool(parsed.get("--include-members")),
        "include_users_details": bool(parsed.get("--include-users-details")),
        "filter_by_member_role": (
            parsed.get("--role")
            if isinstance(parsed.get("--role"), list)
            else ([parsed.get("--role")] if parsed.get("--role") else None)
        ),
        # invert include-empty to exclude_empty_groups
        "exclude_empty_groups": False if parsed.get("--include-empty") else True,
        # target_user; validator will default to requestor when None
        "target_member_email": parsed.get("--user"),
        # filter_by_member_email: let validator set default based on include_members
        "filter_by_member_email": None,
    }
    return mapped


def handle_groups_list_command(
    payload: CommandPayload,
    parsed_args: Dict[str, Any],
    request: schemas.ListGroupsRequest,
) -> CommandResponse:
    """Handle /sre groups list Slack command.

    Args:
        payload: Command payload from Slack platform provider
        parsed_args: Parsed command arguments
        request: Validated ListGroupsRequest

    Returns:
        CommandResponse formatted for Slack
    """
    log = logger.bind(
        command="groups.list", user_id=payload.user_id, channel_id=payload.channel_id
    )
    log.info("slack_command_received", text=payload.text, args=parsed_args)

    try:
        groups = service.list_groups(request)
        count = len(groups) if groups else 0
        if count == 0:
            return CommandResponse(message="No groups found.", ephemeral=True)

        # Basic summary; richer formatting (blocks) can follow in next steps
        lines = []
        for g in groups[:20]:  # cap summary to first 20
            name = g.get("name") if isinstance(g, dict) else getattr(g, "name", None)
            gid = g.get("id") if isinstance(g, dict) else getattr(g, "id", None)
            provider = (
                g.get("provider")
                if isinstance(g, dict)
                else getattr(g, "provider", None)
            )
            lines.append(
                f"• {name or 'Unnamed'} ({gid or 'N/A'}) - {provider or 'unknown'}"
            )

        summary = f"Found {count} group{'s' if count != 1 else ''}:\n" + "\n".join(
            lines
        )
        return CommandResponse(message=summary, ephemeral=True)
    except Exception as e:
        log.error("groups_list_error", error=str(e))
        return CommandResponse(message="Failed to list groups.", ephemeral=True)


# ---- Argument definitions for `sre groups add` ----
_GROUPS_ADD_ARGUMENTS = [
    Argument(
        name="member_email",
        type=ArgumentType.EMAIL,
        required=True,
        description="Email of member to add",
    ),
    Argument(
        name="group_id",
        type=ArgumentType.STRING,
        required=True,
        description="Group identifier",
    ),
    Argument(
        name="provider",
        type=ArgumentType.CHOICE,
        choices=["google", "okta", "azure", "aws", "slack"],
        required=True,
        description="Provider type",
    ),
    Argument(
        name="justification",
        type=ArgumentType.STRING,
        required=True,
        description="Justification for adding member (minimum 10 characters)",
    ),
]


def _map_add_member_arguments(
    parsed: Dict[str, Any], payload: CommandPayload
) -> Dict[str, Any]:
    """Map parsed arguments to AddMemberRequest fields.

    Adds required requestor field from payload.
    """
    requestor_email: Optional[str] = payload.user_email or None
    if not requestor_email and payload.platform_metadata:
        requestor_email = payload.platform_metadata.get("user_email")

    mapped: Dict[str, Any] = {
        "member_email": parsed.get("member_email"),
        "group_id": parsed.get("group_id"),
        "provider": parsed.get("provider"),
        "justification": parsed.get("justification"),
        "requestor": requestor_email or "requestor@example.com",
    }
    return mapped


def handle_groups_add_command(
    payload: CommandPayload,
    parsed_args: Dict[str, Any],
    request: schemas.AddMemberRequest,
) -> CommandResponse:
    """Handle /sre groups add Slack command.

    Args:
        payload: Command payload from Slack platform provider
        parsed_args: Parsed command arguments
        request: Validated AddMemberRequest

    Returns:
        CommandResponse formatted for Slack
    """
    log = logger.bind(
        command="groups.add",
        user_id=payload.user_id,
        channel_id=payload.channel_id,
    )
    log.info("slack_command_received", text=payload.text, args=parsed_args)

    try:
        result = service.add_member(request)

        # Check if operation was successful
        if hasattr(result, "model_dump"):
            result_dict = result.model_dump()
        elif hasattr(result, "dict"):
            result_dict = result.dict()
        else:
            result_dict = result if isinstance(result, dict) else {}

        success = result_dict.get("success", True)
        if not success:
            error_msg = result_dict.get("error_message", "Failed to add member")
            return CommandResponse(message=f"❌ {error_msg}", ephemeral=True)

        # Format success message
        message = (
            f"✅ Successfully added {request.member_email} to group "
            f"{request.group_id} ({request.provider})"
        )
        return CommandResponse(message=message, ephemeral=True)
    except Exception as e:
        log.error("groups_add_error", error=str(e))
        return CommandResponse(
            message=f"❌ Failed to add member: {str(e)}", ephemeral=True
        )


# ---- Argument definitions for `sre groups remove` ----
_GROUPS_REMOVE_ARGUMENTS = [
    Argument(
        name="member_email",
        type=ArgumentType.EMAIL,
        required=True,
        description="Email of member to remove",
    ),
    Argument(
        name="group_id",
        type=ArgumentType.STRING,
        required=True,
        description="Group identifier",
    ),
    Argument(
        name="provider",
        type=ArgumentType.CHOICE,
        choices=["google", "okta", "azure", "aws", "slack"],
        required=True,
        description="Provider type",
    ),
    Argument(
        name="justification",
        type=ArgumentType.STRING,
        required=True,
        description="Justification for removing member (minimum 10 characters)",
    ),
]


def _map_remove_member_arguments(
    parsed: Dict[str, Any], payload: CommandPayload
) -> Dict[str, Any]:
    """Map parsed arguments to RemoveMemberRequest fields.

    Adds required requestor field from payload.
    """
    requestor_email: Optional[str] = payload.user_email or None
    if not requestor_email and payload.platform_metadata:
        requestor_email = payload.platform_metadata.get("user_email")

    mapped: Dict[str, Any] = {
        "member_email": parsed.get("member_email"),
        "group_id": parsed.get("group_id"),
        "provider": parsed.get("provider"),
        "justification": parsed.get("justification"),
        "requestor": requestor_email or "requestor@example.com",
    }
    return mapped


def handle_groups_remove_command(
    payload: CommandPayload,
    parsed_args: Dict[str, Any],
    request: schemas.RemoveMemberRequest,
) -> CommandResponse:
    """Handle /sre groups remove Slack command.

    Args:
        payload: Command payload from Slack platform provider
        parsed_args: Parsed command arguments
        request: Validated RemoveMemberRequest

    Returns:
        CommandResponse formatted for Slack
    """
    log = logger.bind(
        command="groups.remove",
        user_id=payload.user_id,
        channel_id=payload.channel_id,
    )
    log.info("slack_command_received", text=payload.text, args=parsed_args)

    try:
        result = service.remove_member(request)

        # Check if operation was successful
        if hasattr(result, "model_dump"):
            result_dict = result.model_dump()
        elif hasattr(result, "dict"):
            result_dict = result.dict()
        else:
            result_dict = result if isinstance(result, dict) else {}

        success = result_dict.get("success", True)
        if not success:
            error_msg = result_dict.get("error_message", "Failed to remove member")
            return CommandResponse(message=f"❌ {error_msg}", ephemeral=True)

        # Format success message
        message = (
            f"✅ Successfully removed {request.member_email} from group "
            f"{request.group_id} ({request.provider})"
        )
        return CommandResponse(message=message, ephemeral=True)
    except Exception as e:
        log.error("groups_remove_error", error=str(e))
        return CommandResponse(
            message=f"❌ Failed to remove member: {str(e)}", ephemeral=True
        )


def register_commands(provider: "SlackPlatformProvider") -> None:
    """Register groups module commands with Slack provider.

    Args:
        provider: Slack platform provider instance
    """
    provider.register_command(
        command="list",
        handler=handle_groups_list_command,
        parent="sre.groups",
        description="List groups with flexible filters",
        description_key="groups.slack.list.description",
        usage_hint="[--provider aws] [--include-members] [--role OWNER] [--user email] [--include-empty]",
        examples=[
            "--provider aws",
            "--include-members --role MANAGER",
            "--user user@example.com --include-members --include-users-details",
        ],
        arguments=_GROUPS_LIST_ARGUMENTS,
        schema=schemas.ListGroupsRequest,
        argument_mapper=_map_list_arguments,
    )

    provider.register_command(
        command="add",
        handler=handle_groups_add_command,
        parent="sre.groups",
        description="Add a member to a group",
        description_key="groups.slack.add.description",
        usage_hint="<member_email> <group_id> <provider> <justification>",
        examples=[
            "user@example.com group-123 google 'User joining engineering team'",
            "member@example.com aws-group-456 aws 'Needs access for project work'",
        ],
        arguments=_GROUPS_ADD_ARGUMENTS,
        schema=schemas.AddMemberRequest,
        argument_mapper=_map_add_member_arguments,
    )

    provider.register_command(
        command="remove",
        handler=handle_groups_remove_command,
        parent="sre.groups",
        description="Remove a member from a group",
        description_key="groups.slack.remove.description",
        usage_hint="<member_email> <group_id> <provider> <justification>",
        examples=[
            "user@example.com group-123 google 'User no longer needs access'",
            "member@example.com aws-group-456 aws 'Project completed'",
        ],
        arguments=_GROUPS_REMOVE_ARGUMENTS,
        schema=schemas.RemoveMemberRequest,
        argument_mapper=_map_remove_member_arguments,
    )
