# modules/groups/api/commands.py
"""Command handlers for Slack integration."""

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.logging import get_module_logger
from integrations.slack import users as slack_users
from modules.groups.api import responses, schemas
from modules.groups.core import service
from modules.groups.infrastructure.validation import (
    validate_email,
    validate_provider_type,
)
from modules.groups.providers import get_active_providers
from slack_bolt import Ack, Respond
from slack_sdk import WebClient

logger = get_module_logger()


def handle_groups_command(
    client: WebClient, body: Dict[str, Any], respond: Respond, ack: Ack, args: List[str]
) -> None:
    """Handle the main /sre groups command."""
    ack()

    if not args:
        respond(_get_help_text())
        return

    action = args[0].lower()

    if action in ["help", "--help", "-h"]:
        respond(_get_help_text())
    elif action == "list":
        _handle_list_command(client, body, respond, args[1:])
    elif action == "add":
        _handle_add_command(client, body, respond, args[1:])
    elif action == "remove":
        _handle_remove_command(client, body, respond, args[1:])
    elif action == "manage":
        _handle_manage_command(client, body, respond, args[1:])
    else:
        respond(
            f"Unknown command: {action}. Use `/sre groups help` for available commands."
        )


@dataclass
class ListCommandArgs:
    """Parsed arguments for the list command."""

    provider: Optional[schemas.ProviderType] = None
    target_user_email: Optional[str] = None
    include_details: bool = False
    managed_only: bool = False
    filter_by_roles: Optional[List[str]] = None
    include_empty: bool = False


def _parse_list_args(args: List[str]) -> tuple[ListCommandArgs, Optional[str]]:
    """Parse list command arguments and flags.

    Supports:
    - [provider] - Optional positional provider (aws, google, azure)
    - --user <email> - Target user email (defaults to requestor)
    - --managed - Show only groups where user is MANAGER/OWNER
    - --role <role1,role2> - Filter by member roles
    - --details - Include full user details
    - --include-empty - Include groups with no members

    Returns:
        Tuple of (parsed_args, error_message)
        error_message is None if parsing succeeded
    """
    parsed = ListCommandArgs()
    i = 0

    while i < len(args):
        arg = args[i]

        # Check if it's a provider (positional, no flag)
        if not arg.startswith("--") and not parsed.provider:
            if arg in schemas.ProviderType.__members__.values():
                parsed.provider = schemas.ProviderType(arg)
                i += 1
                continue
            else:
                return (
                    parsed,
                    f"❌ Unknown provider: {arg}. Must be one of: {', '.join(schemas.ProviderType.__members__.values())}",
                )

        # Parse flags
        if arg == "--user":
            if i + 1 >= len(args):
                return parsed, "❌ --user flag requires an email argument"
            parsed.target_user_email = args[i + 1]
            if not validate_email(parsed.target_user_email):
                return parsed, f"❌ Invalid email format: {parsed.target_user_email}"
            i += 2

        elif arg == "--details":
            parsed.include_details = True
            i += 1

        elif arg == "--managed":
            parsed.managed_only = True
            i += 1

        elif arg == "--role":
            if i + 1 >= len(args):
                return parsed, "❌ --role flag requires role argument (comma-separated)"
            role_str = args[i + 1]
            parsed.filter_by_roles = [r.strip().upper() for r in role_str.split(",")]
            i += 2

        elif arg == "--include-empty":
            parsed.include_empty = True
            i += 1

        else:
            return parsed, f"❌ Unknown flag: {arg}"

    return parsed, None


def _handle_list_command(
    client, body: Dict[str, Any], respond: Respond, args: List[str]
) -> None:
    """Handle groups list command with rich flag support.

    Usage:
        /sre groups list [provider] [--user <email>] [--managed] [--role <roles>] [--details]

    Examples:
        /sre groups list                           # Your groups
        /sre groups list google                    # Your Google groups
        /sre groups list --managed                 # Groups you manage
        /sre groups list --role MANAGER,OWNER      # Groups where you're manager/owner
        /sre groups list --user other@example.com  # Other user's groups
    """
    logger.debug("groups_list_command_args", args=args)

    requestor = slack_users.get_user_email_from_body(client, body)
    if not requestor:
        respond("❌ Could not determine your email address.")
        return

    # Parse arguments
    parsed_args, parse_error = _parse_list_args(args)
    if parse_error:
        respond(parse_error)
        return

    # Determine target user (defaults to requestor)
    target_user_email = parsed_args.target_user_email or requestor

    try:
        # Build ListGroupsRequest - always include members and filter by target user
        request_kwargs = {
            "requestor": requestor,
            "target_member_email": target_user_email,
            "provider": parsed_args.provider,
            "include_members": True,
            "filter_by_member_email": target_user_email,
            "include_users_details": parsed_args.include_details,
        }

        # Handle --managed flag (filter by MANAGER/OWNER roles)
        if parsed_args.managed_only:
            request_kwargs["filter_by_member_role"] = ["MANAGER", "OWNER"]

        # Handle --role flag (filter by specific roles)
        if parsed_args.filter_by_roles:
            request_kwargs["filter_by_member_role"] = parsed_args.filter_by_roles

        # Handle --include-empty flag
        if parsed_args.include_empty:
            request_kwargs["exclude_empty_groups"] = False

        req = schemas.ListGroupsRequest(**request_kwargs)

        logger.debug("groups_list_command_request", req=req)
        groups = service.list_groups(req)

        if not groups:
            respond("✅ No groups found matching your criteria.")
            return

        # Format response
        group_stringified = []
        for group in groups:
            if isinstance(group, dict):
                group_name = group.get("name", "Unnamed Group")
                group_id = group.get("id", "N/A")
                members = group.get("members", [])

                # Show target user's role in the group
                user = next(
                    (u for u in members if u.get("email") == target_user_email),
                    None,
                )
                role = user.get("role", "MEMBER") if user else "N/A"

                group_stringified.append(f"• {group_name} (ID: {group_id}) - {role}")

        # Build summary line
        summary = f"✅ Retrieved {len(groups)} group{'s' if len(groups) != 1 else ''}"
        if parsed_args.managed_only:
            summary += " (managed)"
        if parsed_args.filter_by_roles and not parsed_args.managed_only:
            summary += f" (roles: {', '.join(parsed_args.filter_by_roles)})"
        if target_user_email != requestor:
            summary += f" for {target_user_email}"

        respond(f"{summary}:\n" + "\n".join(group_stringified))

    except ValueError as e:
        logger.error(f"Validation error in groups list command: {e}")
        respond(f"❌ Invalid input: {str(e)}")
    except Exception as e:
        logger.error(f"Error in groups list command: {e}")
        respond("❌ Error retrieving your groups. Please try again later.")


def _handle_add_command(
    client, body: Dict[str, Any], respond: Respond, args: List[str]
) -> None:
    """Handle groups add command."""
    if len(args) < 3:
        respond(
            "❌ Usage: `/sre groups add <member_email> <group_id> <provider> [justification]`"
        )
        return

    # could be either email or slack handle; if starts with @ try resolving to email
    member_email = args[0]
    if member_email.startswith("@"):
        resolved_email = slack_users.get_user_email_from_handle(client, member_email)
        if not resolved_email:
            respond(f"❌ Could not resolve Slack handle {member_email} to an email.")
            return
        member_email = resolved_email
    group_id = args[1].lower()
    provider_type = args[2]
    justification = " ".join(args[3:]) if len(args) > 3 else "Added via Slack command"

    # Validate inputs
    if not validate_email(member_email):
        respond(f"❌ Invalid email format: {member_email}")
        return

    if not validate_provider_type(provider_type):
        respond("❌ Invalid provider. Must be one of: aws, google, azure")
        return

    requestor_email = slack_users.get_user_email_from_body(client, body)
    if not requestor_email:
        respond("❌ Could not determine your email address.")
        return

    try:
        # Build Pydantic request and call service directly. Coerce provider to
        # the ProviderType enum so downstream code receives normalized types.
        add_req = schemas.AddMemberRequest(
            group_id=group_id,
            member_email=member_email,
            provider=schemas.ProviderType(provider_type),
            justification=justification,
            requestor=requestor_email,
            idempotency_key=str(uuid.uuid4()),
        )
        result = service.add_member(add_req)

        # Format Slack-friendly text
        respond(
            responses.format_slack_response(
                result.model_dump() if hasattr(result, "model_dump") else result.dict()
            )
        )
    except Exception as e:
        logger.error(f"Error in groups add command: {e}")
        respond("❌ Error adding member to group. Please try again later.")


def _handle_remove_command(
    client, body: Dict[str, Any], respond: Respond, args: List[str]
) -> None:
    """Handle groups remove command."""
    if len(args) < 3:
        respond(
            "❌ Usage: `/sre groups remove <member_email> <group_id> <provider> [justification]`"
        )
        return

    # could be either email or slack handle; if starts with @ try resolving to email
    member_email = args[0]
    if member_email.startswith("@"):
        resolved_email = slack_users.get_user_email_from_handle(client, member_email)
        if not resolved_email:
            respond(f"❌ Could not resolve Slack handle {member_email} to an email.")
            return
        member_email = resolved_email
    group_id = args[1].lower()
    provider_type = args[2].lower()
    justification = " ".join(args[3:]) if len(args) > 3 else "Removed via Slack command"

    # Validate inputs
    if not validate_email(member_email):
        respond(f"❌ Invalid email format: {member_email}")
        return

    if not validate_provider_type(provider_type):
        respond("❌ Invalid provider. Must be one of: aws, google, azure")
        return

    requestor_email = slack_users.get_user_email_from_body(client, body)
    if not requestor_email:
        respond("❌ Could not determine your email address.")
        return

    try:
        remove_req = schemas.RemoveMemberRequest(
            group_id=group_id,
            member_email=member_email,
            provider=schemas.ProviderType(provider_type),
            justification=justification,
            requestor=requestor_email,
            idempotency_key=str(uuid.uuid4()),
        )
        result = service.remove_member(remove_req)
        respond(
            responses.format_slack_response(
                result.model_dump() if hasattr(result, "model_dump") else result.dict()
            )
        )
    except Exception as e:
        logger.error(f"Error in groups remove command: {e}")
        respond("❌ Error removing member from group. Please try again later.")


def _handle_manage_command(
    client, body: Dict[str, Any], respond: Respond, args: List[str]
):
    """Handle groups manage command. Lists all manageable groups for the user."""
    user_email = slack_users.get_user_email_from_body(client, body)
    if not user_email:
        respond("❌ Could not determine your email address.")
        return

    provider_type = None
    if args and args[0] in ["aws", "google", "azure"]:
        provider_type = schemas.ProviderType(args[0])
    logger.debug("provider_type_in_manage_command", provider_type=provider_type)
    try:
        req = (
            schemas.ListGroupsRequest(
                requestor=user_email,
                include_members=True,
                target_member_email=user_email,
                provider=provider_type,
            )
            if provider_type
            else schemas.ListGroupsRequest(requestor=user_email)
        )
        groups = service.list_groups(req)
        respond(f"✅ Retrieved {len(groups)} manageable groups")
    except Exception as e:
        logger.error(f"Error in groups list command: {e}")
        respond("❌ Error retrieving your groups. Please try again later.")


def _get_help_text() -> str:
    """Get help text for groups commands."""
    active_providers = get_active_providers().keys()
    return f"""
🔐 *Groups Membership Management*

Available commands:

• `/sre groups list [provider]` - List groups you can manage
• `/sre groups add <email> <group_id> <provider> [justification]` - Add member to group
• `/sre groups remove <email> <group_id> <provider> [justification]` - Remove member from group
• `/sre groups help` - Show this help

*Active Providers:* {', '.join(active_providers)}

*Examples:*
• `/sre groups list aws`
• `/sre groups add user@example.com my-group aws "Adding for project access"`
• `/sre groups remove user@example.com my-group aws "No longer needed"`

*Note:* You can only manage groups where you have admin/manager permissions.
""".strip()


def register_groups_commands(bot):
    """Register groups commands with the Slack bot."""
    # This would be called from your main registration function
    # bot.command("/sre")(handle_sre_command)  # You'd route 'groups' subcommand to handle_groups_command
    logger.info(
        "Groups commands registration placeholder - integrate with your existing SRE command router"
    )
