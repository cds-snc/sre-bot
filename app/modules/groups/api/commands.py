# modules/groups/api/commands.py
"""Command handlers for Slack integration."""

import uuid
from typing import Dict, Any, List
from slack_sdk import WebClient
from slack_bolt import Ack, Respond

from core.logging import get_module_logger
from modules.groups.core import service
from modules.groups.api import responses, schemas
from modules.groups.providers import get_active_providers
from modules.groups.infrastructure.validation import (
    validate_email,
    validate_provider_type,
)
from integrations.slack import users as slack_users


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
    elif action == "providers":
        _handle_list_active_providers_command(client, body, respond, args[1:])
    else:
        respond(
            f"Unknown command: {action}. Use `/sre groups help` for available commands."
        )


def _handle_list_command(
    client, body: Dict[str, Any], respond: Respond, args: List[str]
) -> None:
    """Handle groups list command."""
    user_email = slack_users.get_user_email_from_body(client, body)
    if not user_email:
        respond("❌ Could not determine your email address.")
        return

    provider_type = None
    if args and args[0] in ["aws", "google", "azure"]:
        provider_type = schemas.ProviderType(args[0])

    try:
        req = (
            schemas.ListGroupsRequest(user_email=user_email, provider=provider_type)
            if provider_type
            else schemas.ListGroupsRequest(user_email=user_email)
        )
        groups = service.list_groups(req)
        # Simple user-friendly Slack message
        group_stringified = []
        if len(groups) > 0:
            logger.debug("logging_single_group_for_list_command", group=groups[0])
        for group in groups:
            if isinstance(group, dict):
                user = next(
                    (
                        u
                        for u in group.get("members", [])
                        if u.get("email") == user_email
                    ),
                    None,
                )
                group_stringified.append(
                    f"\n- {group.get('name', 'Unnamed Group')} (ID: {group.get('id', 'N/A')}) - {user.get('role', 'N/A') if user else 'N/A'}"
                )
        respond(f"✅ Retrieved {len(groups)} groups:\n" + "\n".join(group_stringified))
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

    try:
        req = (
            schemas.ListGroupsRequest(user_email=user_email, provider=provider_type)
            if provider_type
            else schemas.ListGroupsRequest(user_email=user_email)
        )
        groups = service.list_groups(req)
        respond(f"✅ Retrieved {len(groups)} manageable groups")
    except Exception as e:
        logger.error(f"Error in groups list command: {e}")
        respond("❌ Error retrieving your groups. Please try again later.")


def _handle_list_active_providers_command(
    client, body: Dict[str, Any], respond: Respond, args: List[str]
):
    """Handle groups providers command."""
    active_providers = get_active_providers().keys()
    respond(f"✅ Active group providers: {', '.join(active_providers)}")


def _get_help_text() -> str:
    """Get help text for groups commands."""
    return """
🔐 **Groups Membership Management**

Available commands:
• `/sre groups list [provider]` - List groups you can manage
• `/sre groups add <email> <group_id> <provider> [justification]` - Add member to group
• `/sre groups remove <email> <group_id> <provider> [justification]` - Remove member from group
• `/sre groups help` - Show this help

**Providers:** aws, google, azure

**Examples:**
• `/sre groups list aws`
• `/sre groups add user@example.com my-group aws "Adding for project access"`
• `/sre groups remove user@example.com my-group aws "No longer needed"`

**Note:** You can only manage groups where you have admin/manager permissions.
""".strip()


def register_groups_commands(bot):
    """Register groups commands with the Slack bot."""
    # This would be called from your main registration function
    # bot.command("/sre")(handle_sre_command)  # You'd route 'groups' subcommand to handle_groups_command
    logger.info(
        "Groups commands registration placeholder - integrate with your existing SRE command router"
    )
