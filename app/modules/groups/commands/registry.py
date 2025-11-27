"""Command registry for groups module."""

from typing import Dict, Any
from infrastructure.commands import (
    CommandRegistry,
    CommandContext,
    Argument,
    ArgumentType,
)
from modules.groups.api import schemas
from modules.groups.core import service
from modules.groups.commands import responses
from core.logging import get_module_logger

logger = get_module_logger()

# Create registry for groups commands
registry = CommandRegistry(namespace="groups")


def _list_command_mapper(parsed_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Map parsed CLI arguments to ListGroupsRequest fields.

    Transforms flag-based arguments into schema fields:
    - --managed: Sets filter_by_member_role to MANAGER/OWNER roles
    - --role: Parses comma-separated roles
    - --include-empty: Inverts to exclude_empty_groups
    - --details: Maps to include_users_details
    - --user: Maps to target_member_email
    """
    # Handle --user flag
    if "--user" in parsed_kwargs and parsed_kwargs["--user"]:
        parsed_kwargs["target_member_email"] = parsed_kwargs.pop("--user")

    # Handle --managed flag
    if parsed_kwargs.get("--managed"):
        parsed_kwargs["filter_by_member_role"] = ["MANAGER", "OWNER"]
        parsed_kwargs["include_members"] = True

    # Handle --role flag
    role_arg = parsed_kwargs.get("--role")
    if role_arg:
        # Parse comma-separated roles
        roles = [r.strip().upper() for r in role_arg.split(",")]
        parsed_kwargs["filter_by_member_role"] = roles
        parsed_kwargs["include_members"] = True

    # Handle --details flag
    if parsed_kwargs.get("--details"):
        parsed_kwargs["include_users_details"] = True
        parsed_kwargs["include_members"] = True

    # Handle --include-empty flag (invert to exclude_empty_groups)
    parsed_kwargs["exclude_empty_groups"] = not parsed_kwargs.get(
        "--include-empty", False
    )

    # Always include members for filtering/display
    parsed_kwargs["include_members"] = True
    parsed_kwargs["filter_by_member_email"] = parsed_kwargs.get("target_member_email")

    # Clean up flag arguments that aren't in schema
    for key in ["--managed", "--role", "--details", "--include-empty", "--user"]:
        parsed_kwargs.pop(key, None)

    return parsed_kwargs


@registry.schema_command(
    name="list",
    schema=schemas.ListGroupsRequest,
    description_key="groups.commands.list.description",
    mapper=_list_command_mapper,
    args=[
        Argument(
            name="--managed",
            type=ArgumentType.BOOLEAN,
            required=False,
            flag=True,
            description="Filter to managed groups (MANAGER/OWNER roles)",
            description_key="groups.args.managed.description",
        ),
        Argument(
            name="--role",
            type=ArgumentType.STRING,
            required=False,
            flag=True,
            description="Filter by comma-separated roles (e.g., MANAGER,OWNER)",
            description_key="groups.args.role.description",
        ),
        Argument(
            name="--details",
            type=ArgumentType.BOOLEAN,
            required=False,
            flag=True,
            description="Include full user details in members list",
            description_key="groups.args.details.description",
        ),
        Argument(
            name="--include-empty",
            type=ArgumentType.BOOLEAN,
            required=False,
            flag=True,
            description="Include groups with no members",
            description_key="groups.args.include_empty.description",
        ),
        Argument(
            name="--user",
            type=ArgumentType.EMAIL,
            required=False,
            flag=True,
            description="List groups for a specific user (email)",
            description_key="groups.args.user.description",
        ),
        Argument(
            name="provider",
            type=ArgumentType.STRING,
            required=False,
            description="Filter by provider (google, aws, azure)",
            description_key="groups.args.provider.description",
            choices=["aws", "google", "azure"],
        ),
    ],
)
def list_groups_command(
    ctx: CommandContext, request: schemas.ListGroupsRequest
) -> None:
    """List groups you can manage."""
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
    except Exception as e:
        logger.error("groups_list_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.list_failed"))


@registry.schema_command(
    name="add",
    schema=schemas.AddMemberRequest,
    description_key="groups.commands.add.description",
    args=[
        Argument(
            name="member_email",
            type=ArgumentType.EMAIL,
            required=True,
            description="Email of member to add (or @slackhandle)",
            description_key="groups.args.member_email.description",
        ),
        Argument(
            name="group_id",
            type=ArgumentType.STRING,
            required=True,
            description="Group identifier",
            description_key="groups.args.group_id.description",
        ),
        Argument(
            name="provider",
            type=ArgumentType.STRING,
            required=True,
            choices=["aws", "google", "azure"],
            description="Cloud provider",
            description_key="groups.args.provider.description",
        ),
        Argument(
            name="justification",
            type=ArgumentType.STRING,
            required=True,
            description="Justification for adding member (required for audit trail)",
            description_key="groups.args.justification_add.description",
        ),
    ],
)
def add_member_command(ctx: CommandContext, request: schemas.AddMemberRequest) -> None:
    """Add member to group."""
    try:
        result = service.add_member(request)
        ctx.respond(
            responses.format_action_response(ctx, result, operation="add_member")
        )
    except Exception as e:
        logger.error("groups_add_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.add_failed"))


@registry.schema_command(
    name="remove",
    schema=schemas.RemoveMemberRequest,
    description_key="groups.commands.remove.description",
    args=[
        Argument(
            name="member_email",
            type=ArgumentType.EMAIL,
            required=True,
            description="Email of member to remove (or @slackhandle)",
            description_key="groups.args.member_email.description",
        ),
        Argument(
            name="group_id",
            type=ArgumentType.STRING,
            required=True,
            description="Group identifier",
            description_key="groups.args.group_id.description",
        ),
        Argument(
            name="provider",
            type=ArgumentType.STRING,
            required=True,
            choices=["aws", "google", "azure"],
            description="Cloud provider",
            description_key="groups.args.provider.description",
        ),
        Argument(
            name="justification",
            type=ArgumentType.STRING,
            required=True,
            description="Justification for removing member (required for audit trail)",
            description_key="groups.args.justification_remove.description",
        ),
    ],
)
def remove_member_command(
    ctx: CommandContext, request: schemas.RemoveMemberRequest
) -> None:
    """Remove member from group."""
    try:
        result = service.remove_member(request)
        ctx.respond(
            responses.format_action_response(ctx, result, operation="remove_member")
        )
    except Exception as e:
        logger.error("groups_remove_error", error=str(e))
        ctx.respond(ctx.translate("groups.errors.remove_failed"))
