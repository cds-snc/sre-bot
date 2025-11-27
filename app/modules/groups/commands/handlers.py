"""Command handlers for groups module using infrastructure framework."""

import uuid
from typing import List, Optional

from core.logging import get_module_logger
from infrastructure.commands import CommandContext
from integrations.slack import users as slack_users
from modules.groups.api import schemas, responses
from modules.groups.core import service

logger = get_module_logger()


def handle_list(
    ctx: CommandContext,
    provider: Optional[str] = None,
    user_email: Optional[str] = None,
    managed_only: bool = False,
    filter_by_roles: Optional[List[str]] = None,
    include_details: bool = False,
    include_empty: bool = False,
) -> None:
    """Handle groups list command."""
    # Get requestor email from context
    requestor = ctx.user_email
    if not requestor:
        ctx.respond(ctx.translate("groups.errors.no_email"))
        return

    # Determine target user (defaults to requestor)
    target_user_email = user_email if user_email else requestor

    try:
        # Build request with explicit typed arguments to satisfy static typing
        provider_type = schemas.ProviderType(provider) if provider else None

        # Determine role filters
        if managed_only:
            filter_roles = ["MANAGER", "OWNER"]
        elif filter_by_roles:
            filter_roles = filter_by_roles
        else:
            filter_roles = None

        exclude_empty_groups = not include_empty

        req = schemas.ListGroupsRequest(
            requestor=requestor,
            target_member_email=target_user_email,
            include_members=True,
            filter_by_member_email=target_user_email,
            include_users_details=include_details,
            provider=provider_type,
            filter_by_member_role=filter_roles,
            exclude_empty_groups=exclude_empty_groups,
        )
        groups = service.list_groups(req)

        if not groups:
            ctx.respond(ctx.translate("groups.success.no_groups"))
            return

        # Format response
        group_lines = []
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

                group_lines.append(f"• {group_name} (ID: {group_id}) - {role}")

        # Build summary line with i18n
        count = len(groups)
        plural = "s" if count != 1 else ""

        if managed_only:
            summary = ctx.translate(
                "groups.success.list_managed",
                count=count,
                plural=plural,
            )
        elif filter_by_roles and not managed_only:
            summary = ctx.translate(
                "groups.success.list_filtered",
                count=count,
                plural=plural,
                roles=", ".join(filter_by_roles),
            )
        elif target_user_email != requestor:
            summary = ctx.translate(
                "groups.success.list_for_user",
                count=count,
                plural=plural,
                email=target_user_email,
            )
        else:
            summary = ctx.translate(
                "groups.success.list_summary",
                count=count,
                plural=plural,
            )

        ctx.respond(f"{summary}:\n" + "\n".join(group_lines))

    except ValueError as e:
        logger.error("groups_list_validation_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.list_failed"))
    except Exception as e:
        logger.error("groups_list_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.list_failed"))


def handle_add(
    ctx: CommandContext,
    member_email: str,
    group_id: str,
    provider: str,
    justification: str,
) -> None:
    """Handle groups add command."""
    # Resolve Slack handles to emails
    if member_email.startswith("@"):
        # Get Slack client from context metadata
        slack_client = ctx.metadata.get("slack_client")
        if slack_client:
            resolved_email = slack_users.get_user_email_from_handle(
                slack_client, member_email
            )
            if not resolved_email:
                ctx.respond(
                    ctx.translate(
                        "groups.errors.slack_handle_not_found", handle=member_email
                    )
                )
                return
            member_email = resolved_email

    # Get requestor email
    requestor_email = ctx.metadata.get("user_email")
    if not requestor_email:
        ctx.respond(ctx.translate("groups.errors.no_email"))
        return

    try:
        # Build request
        add_req = schemas.AddMemberRequest(
            group_id=group_id,
            member_email=member_email,
            provider=schemas.ProviderType(provider),
            justification=justification,
            requestor=requestor_email,
            idempotency_key=str(uuid.uuid4()),
        )
        result = service.add_member(add_req)

        ctx.respond(
            responses.format_slack_response(
                result.model_dump() if hasattr(result, "model_dump") else result.dict()
            )
        )
    except Exception as e:
        logger.error("groups_add_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.add_failed"))


def handle_remove(
    ctx: CommandContext,
    member_email: str,
    group_id: str,
    provider: str,
    justification: str,
) -> None:
    """Handle groups remove command."""
    # Resolve Slack handles to emails
    if member_email.startswith("@"):
        slack_client = ctx.metadata.get("slack_client")
        if slack_client:
            resolved_email = slack_users.get_user_email_from_handle(
                slack_client, member_email
            )
            if not resolved_email:
                ctx.respond(
                    ctx.translate(
                        "groups.errors.slack_handle_not_found", handle=member_email
                    )
                )
                return
            member_email = resolved_email

    # Get requestor email
    requestor_email = ctx.metadata.get("user_email")
    if not requestor_email:
        ctx.respond(ctx.translate("groups.errors.no_email"))
        return

    try:
        remove_req = schemas.RemoveMemberRequest(
            group_id=group_id,
            member_email=member_email,
            provider=schemas.ProviderType(provider),
            justification=justification,
            requestor=requestor_email,
            idempotency_key=str(uuid.uuid4()),
        )
        result = service.remove_member(remove_req)

        ctx.respond(
            responses.format_slack_response(
                result.model_dump() if hasattr(result, "model_dump") else result.dict()
            )
        )
    except Exception as e:
        logger.error("groups_remove_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.remove_failed"))


def handle_manage(ctx: CommandContext, provider: Optional[str] = None) -> None:
    """Handle groups manage command."""
    user_email = ctx.metadata.get("user_email")
    if not user_email:
        ctx.respond(ctx.translate("groups.errors.no_email"))
        return

    provider_type = None
    if provider:
        provider_type = schemas.ProviderType(provider)

    try:
        req = schemas.ListGroupsRequest(
            requestor=user_email,
            include_members=True,
            target_member_email=user_email,
            provider=provider_type,
        )
        groups = service.list_groups(req)

        if not groups:
            ctx.respond(ctx.translate("groups.success.no_groups"))
            return

        # Format response
        group_lines = []
        for group in groups:
            if isinstance(group, dict):
                group_name = group.get("name", "Unnamed Group")
                group_id = group.get("id", "N/A")
                group_lines.append(f"• {group_name} (ID: {group_id})")

        count = len(groups)
        plural = "s" if count != 1 else ""
        summary = ctx.translate(
            "groups.success.list_managed",
            count=count,
            plural=plural,
        )
        ctx.respond(f"{summary}:\n" + "\n".join(group_lines))
    except Exception as e:
        logger.error("groups_manage_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.list_failed"))


def handle_help(ctx: CommandContext) -> None:
    """Handle help command."""
    help_text = ctx.translate("groups.commands.list.help")
    ctx.respond(help_text)
