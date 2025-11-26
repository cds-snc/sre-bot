"""Command registry for groups module."""

from infrastructure.commands import CommandRegistry, Argument, ArgumentType
from modules.groups.commands import handlers

# Create registry for groups commands
registry = CommandRegistry(namespace="groups")


@registry.command(
    name="list",
    description_key="groups.commands.list.description",
    args=[
        Argument(
            name="provider",
            type=ArgumentType.STRING,
            required=False,
            choices=["aws", "google", "azure"],
            description="Cloud provider (aws, google, azure)",
        ),
        Argument(
            name="--user",
            type=ArgumentType.EMAIL,
            required=False,
            flag=True,
            description="Target user email (defaults to requestor)",
        ),
        Argument(
            name="--managed",
            type=ArgumentType.BOOLEAN,
            required=False,
            flag=True,
            default=False,
            description="Show only groups where you are manager/owner",
        ),
        Argument(
            name="--role",
            type=ArgumentType.STRING,
            required=False,
            flag=True,
            description="Filter by member roles (comma-separated)",
        ),
        Argument(
            name="--details",
            type=ArgumentType.BOOLEAN,
            required=False,
            flag=True,
            default=False,
            description="Include full user details",
        ),
        Argument(
            name="--include-empty",
            type=ArgumentType.BOOLEAN,
            required=False,
            flag=True,
            default=False,
            description="Include groups with no members",
        ),
    ],
)
def list_groups_command(
    ctx,
    provider=None,
    **kwargs,
):
    """List groups you can manage."""
    # Extract flag values from kwargs
    user_email = kwargs.get("--user")
    managed_only = kwargs.get("--managed", False)
    filter_by_roles = kwargs.get("--role")
    include_details = kwargs.get("--details", False)
    include_empty = kwargs.get("--include-empty", False)

    return handlers.handle_list(
        ctx,
        provider=provider,
        user_email=user_email,
        managed_only=managed_only,
        filter_by_roles=filter_by_roles.split(",") if filter_by_roles else None,
        include_details=include_details,
        include_empty=include_empty,
    )


@registry.command(
    name="add",
    description_key="groups.commands.add.description",
    args=[
        Argument(
            name="member_email",
            type=ArgumentType.EMAIL,
            required=True,
            description="Email of member to add (or @slackhandle)",
        ),
        Argument(
            name="group_id",
            type=ArgumentType.STRING,
            required=True,
            description="Group identifier",
        ),
        Argument(
            name="provider",
            type=ArgumentType.STRING,
            required=True,
            choices=["aws", "google", "azure"],
            description="Cloud provider",
        ),
        Argument(
            name="justification",
            type=ArgumentType.STRING,
            required=False,
            description="Justification for adding member",
        ),
    ],
)
def add_member_command(ctx, member_email, group_id, provider, justification=None):
    """Add member to group."""
    return handlers.handle_add(
        ctx,
        member_email=member_email,
        group_id=group_id,
        provider=provider,
        justification=justification or "Added via Slack command",
    )


@registry.command(
    name="remove",
    description_key="groups.commands.remove.description",
    args=[
        Argument(
            name="member_email",
            type=ArgumentType.EMAIL,
            required=True,
            description="Email of member to remove (or @slackhandle)",
        ),
        Argument(
            name="group_id",
            type=ArgumentType.STRING,
            required=True,
            description="Group identifier",
        ),
        Argument(
            name="provider",
            type=ArgumentType.STRING,
            required=True,
            choices=["aws", "google", "azure"],
            description="Cloud provider",
        ),
        Argument(
            name="justification",
            type=ArgumentType.STRING,
            required=False,
            description="Justification for removing member",
        ),
    ],
)
def remove_member_command(ctx, member_email, group_id, provider, justification=None):
    """Remove member from group."""
    return handlers.handle_remove(
        ctx,
        member_email=member_email,
        group_id=group_id,
        provider=provider,
        justification=justification or "Removed via Slack command",
    )


@registry.command(
    name="manage",
    description_key="groups.commands.manage.description",
    args=[
        Argument(
            name="provider",
            type=ArgumentType.STRING,
            required=False,
            choices=["aws", "google", "azure"],
            description="Cloud provider filter",
        ),
    ],
)
def manage_groups_command(ctx, provider=None):
    """List all manageable groups."""
    return handlers.handle_manage(ctx, provider=provider)


@registry.command(
    name="help",
    description_key="groups.commands.list.help",
)
def help_command(ctx):
    """Show help for groups commands."""
    return handlers.handle_help(ctx)
