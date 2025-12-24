"""Command handlers for groups module.

This module contains the actual command handler implementations that are registered
with the CommandRegistry. Each handler is a thin adapter that:
1. Receives CommandContext and validated Pydantic request
2. Calls service layer (platform-agnostic business logic)
3. Formats and sends response using i18n translations

Handlers are kept separate from registry.py for cleaner separation of concerns:
- registry.py: Command definitions and registration metadata
- handlers.py: Command implementation logic
"""

import structlog
from infrastructure.commands import CommandContext
from modules.groups.api import schemas
from modules.groups.core import service
from modules.groups.commands import responses

logger = structlog.get_logger()


def list_groups_command(
    ctx: CommandContext, request: schemas.ListGroupsRequest
) -> None:
    """List groups you can manage.

    Handles the /sre groups list command with support for filtering by:
    - Provider (aws, google, azure)
    - Member role (--managed, --role)
    - Target user (--user)
    - Inclusion of members (--details, --include-empty)

    Args:
        ctx: CommandContext with user info, locale, and translator
        request: Validated ListGroupsRequest with filter parameters
    """
    logger.warning("groups_list_command_invoked", request=request, ctx=ctx)
    try:
        groups = service.list_groups(request)

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
                target_email = request.target_member_email or request.requestor
                user = next(
                    (u for u in members if u.get("email") == target_email),
                    None,
                )
                role = user.get("role", "MEMBER") if user else "N/A"

                group_lines.append(f"• {group_name} (ID: {group_id}) - {role}")

        # Build summary with context-aware translation
        count = len(groups)
        plural = "s" if count != 1 else ""

        # Determine which summary to show based on filters
        if request.filter_by_member_role and "MANAGER" in request.filter_by_member_role:
            # Managed groups
            summary = ctx.translate(
                "groups.success.list_managed",
                count=count,
                plural=plural,
            )
        elif request.filter_by_member_role:
            # Filtered by specific roles
            summary = ctx.translate(
                "groups.success.list_filtered",
                count=count,
                plural=plural,
                roles=", ".join(request.filter_by_member_role),
            )
        elif (
            request.target_member_email
            and request.target_member_email != request.requestor
        ):
            # User's groups (not requestor)
            summary = ctx.translate(
                "groups.success.list_for_user",
                count=count,
                plural=plural,
                email=request.target_member_email,
            )
        else:
            # Default: requestor's groups
            summary = ctx.translate(
                "groups.success.list_summary",
                count=count,
                plural=plural,
            )

        ctx.respond(f"{summary}:\n" + "\n".join(group_lines))

    except ValueError as e:
        logger.error("groups_list_validation_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.list_failed"))
    except Exception as e:  # pylint: disable=broad-except
        logger.error("groups_list_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.list_failed"))


def add_member_command(ctx: CommandContext, request: schemas.AddMemberRequest) -> None:
    """Add member to group.

    Handles the /sre groups add command to add a user to a group.
    Requires:
    - member_email: Email of user to add (or @slackhandle)
    - group_id: Group identifier
    - provider: Cloud provider (aws, google, azure)
    - justification: Reason for addition (required for audit trail)

    Args:
        ctx: CommandContext with user info, locale, and translator
        request: Validated AddMemberRequest with member and group details
    """
    try:
        result = service.add_member(request)
        ctx.respond(
            responses.format_action_response(ctx, result, operation="add_member")
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error("groups_add_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.add_failed"))


def remove_member_command(
    ctx: CommandContext, request: schemas.RemoveMemberRequest
) -> None:
    """Remove member from group.

    Handles the /sre groups remove command to remove a user from a group.
    Requires:
    - member_email: Email of user to remove (or @slackhandle)
    - group_id: Group identifier
    - provider: Cloud provider (aws, google, azure)
    - justification: Reason for removal (required for audit trail)

    Args:
        ctx: CommandContext with user info, locale, and translator
        request: Validated RemoveMemberRequest with member and group details
    """
    try:
        result = service.remove_member(request)
        ctx.respond(
            responses.format_action_response(ctx, result, operation="remove_member")
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error("groups_remove_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.remove_failed"))
