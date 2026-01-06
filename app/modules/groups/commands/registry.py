"""Command registry for groups module.

This module defines the command registry and registration metadata (names, arguments,
descriptions, etc.). The actual handler implementations are in handlers.py.

This separation provides:
- Cleaner registry file focused on command definitions
- Handler logic isolated in separate module for testability
- Easier to scale as module grows with more commands
"""

from typing import Dict, Any
import structlog
from infrastructure.commands import (
    CommandRegistry,
    Argument,
    ArgumentType,
)
from modules.groups.api import schemas
from modules.groups.commands import handlers


logger = structlog.get_logger()

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
    description="List groups.",
    description_key="groups.commands.list.description",
    mapper=_list_command_mapper,  # Keep this - complex field mapping logic
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
def list_groups_command(*args, **kwargs):
    """List groups you can manage."""
    return handlers.list_groups_command(*args, **kwargs)


def _add_member_mapper(parsed_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    return parsed_kwargs


@registry.schema_command(
    name="add",
    schema=schemas.AddMemberRequest,
    description_key="groups.commands.add.description",
    mapper=_add_member_mapper,
    # No mapper needed - preprocessing handled by SlackCommandProvider
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
def add_member_command(*args, **kwargs):
    """Add member to group."""
    return handlers.add_member_command(*args, **kwargs)


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
def remove_member_command(*args, **kwargs):
    """Remove member from group."""
    return handlers.remove_member_command(*args, **kwargs)
