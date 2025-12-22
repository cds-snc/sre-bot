"""AWS Client Testing Module - Development commands for testing AWS integrations.

This module provides safe, read-only testing commands for AWS service clients.
Each AWS service (IdentityStore, Organizations, SSO Admin, etc.) has its own
command registry with testable operations.

Usage:
    /dev aws identitystore healthcheck
    /dev aws organizations list-accounts
    /dev aws sso list-permission-sets
    /dev aws health check
"""

import json
import structlog

from infrastructure.commands.router import CommandRouter
from infrastructure.commands.providers.slack import SlackCommandProvider
from infrastructure.commands.registry import CommandRegistry
from infrastructure.services.providers import get_aws_clients
from infrastructure.commands.responses.models import (
    Card,
    ErrorMessage,
    SuccessMessage,
)

logger = structlog.get_logger()

# ============================================================
# AWS DEV COMMAND ROUTER
# ============================================================

aws_dev_router = CommandRouter(namespace="sre dev aws")


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def send_operation_result(
    ctx, result, operation_name: str, max_items: int = 10
) -> None:
    """Send an OperationResult using platform-agnostic response models.

    Uses SuccessMessage, ErrorMessage, and Card via the context responder,
    allowing Slack (and future providers) to format appropriately.

    Args:
        ctx: CommandContext for responding
        result: OperationResult from AWS operation
        operation_name: Name of the operation for display
        max_items: Maximum number of list items to preview
    """
    if not result.is_success:
        ctx.respond_error(
            ErrorMessage(
                message=f"{operation_name} failed", details=str(result.message)
            )
        )
        return

    data = result.data
    if data is None:
        ctx.respond_success(SuccessMessage(message=f"{operation_name} succeeded"))
        return

    if isinstance(data, dict):
        item_count = len(data)
        preview = json.dumps(data, indent=2, default=str)
        if len(preview) > 500:
            preview = preview[:500] + "\n... (truncated)"
        ctx.respond_card(
            Card(
                title=f"{operation_name} succeeded",
                text=f"{item_count} keys in response\n```{preview}```",
            )
        )
        return

    if isinstance(data, list):
        item_count = len(data)
        preview_items = data[:max_items]
        preview = json.dumps(preview_items, indent=2, default=str)
        if len(preview) > 500:
            preview = preview[:500] + "\n... (truncated)"
        truncated_msg = (
            f" (showing {max_items} of {item_count})" if item_count > max_items else ""
        )
        ctx.respond_card(
            Card(
                title=f"{operation_name} succeeded",
                text=f"{item_count} items{truncated_msg}\n```{preview}```",
            )
        )
        return

    # Scalar or other types
    ctx.respond_success(
        SuccessMessage(message=f"{operation_name} succeeded", details=str(data))
    )


# ============================================================
# IDENTITY STORE COMMANDS
# ============================================================

identitystore_registry = CommandRegistry("identitystore")


@identitystore_registry.command(
    name="healthcheck",
    description="Test IdentityStore client health",
    description_key="dev.aws.identitystore.healthcheck.description",
)
def identitystore_healthcheck(ctx):
    """Test IdentityStore client connectivity and configuration."""
    aws = get_aws_clients()
    result = aws.identitystore.healthcheck()
    send_operation_result(ctx, result, "IdentityStore Healthcheck")


@identitystore_registry.command(
    name="list-users",
    description="List users in Identity Store (first 10)",
    description_key="dev.aws.identitystore.list_users.description",
)
def identitystore_list_users(ctx):
    """List users from Identity Store (limited to first 10 for safety)."""
    aws = get_aws_clients()
    result = aws.identitystore.list_users(max_results=10)
    send_operation_result(ctx, result, "List Users", max_items=10)


@identitystore_registry.command(
    name="list-groups",
    description="List groups in Identity Store (first 10)",
    description_key="dev.aws.identitystore.list_groups.description",
)
def identitystore_list_groups(ctx):
    """List groups from Identity Store (limited to first 10 for safety)."""
    aws = get_aws_clients()
    result = aws.identitystore.list_groups(max_results=10)
    send_operation_result(ctx, result, "List Groups", max_items=10)


# ============================================================
# ORGANIZATIONS COMMANDS
# ============================================================

organizations_registry = CommandRegistry("organizations")


@organizations_registry.command(
    name="list-accounts",
    description="List AWS accounts in the organization (first 10)",
    description_key="dev.aws.organizations.list_accounts.description",
)
def organizations_list_accounts(ctx):
    """List AWS accounts (limited to first 10 for safety)."""
    aws = get_aws_clients()
    result = aws.organizations.list_accounts(MaxResults=10)
    send_operation_result(ctx, result, "List Accounts", max_items=10)


@organizations_registry.command(
    name="describe-organization",
    description="Describe the AWS organization",
    description_key="dev.aws.organizations.describe_organization.description",
)
def organizations_describe_organization(ctx):
    """Get organization details."""
    aws = get_aws_clients()
    result = aws.organizations.describe_organization()
    send_operation_result(ctx, result, "Describe Organization")


# ============================================================
# SSO ADMIN COMMANDS
# ============================================================

sso_admin_registry = CommandRegistry("sso_admin")


@sso_admin_registry.command(
    name="list-permission-sets",
    description="List SSO permission sets (first 10)",
    description_key="dev.aws.sso_admin.list_permission_sets.description",
)
def sso_admin_list_permission_sets(ctx):
    """List SSO permission sets (limited to first 10 for safety)."""
    aws = get_aws_clients()
    result = aws.sso_admin.list_permission_sets(max_results=10)
    send_operation_result(ctx, result, "List Permission Sets", max_items=10)


# ============================================================
# HEALTH CHECK COMMANDS
# ============================================================

health_registry = CommandRegistry("health")


@health_registry.command(
    name="check",
    description="Run comprehensive AWS integration health check",
    description_key="dev.aws.health.check.description",
)
def health_check(ctx):
    """Run comprehensive health check across all AWS services."""
    aws = get_aws_clients()
    result = aws.health.check_all_integrations()

    if result.is_success:
        health_data = result.data
        lines = ["✅ *AWS Integration Health Check*\n"]
        for service, status in health_data.items():
            emoji = "✅" if status.get("healthy", False) else "❌"
            lines.append(f"{emoji} {service}: {status.get('status', 'unknown')}")
        ctx.respond("\n".join(lines))
    else:
        ctx.respond(f"❌ Health check failed: {result.message}")


# ============================================================
# PROVIDER IMPLEMENTATIONS
# ============================================================


class IdentityStoreTestProvider(SlackCommandProvider):
    """Provider for IdentityStore testing commands."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = identitystore_registry


class OrganizationsTestProvider(SlackCommandProvider):
    """Provider for Organizations testing commands."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = organizations_registry


class SSOAdminTestProvider(SlackCommandProvider):
    """Provider for SSO Admin testing commands."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = sso_admin_registry


class HealthTestProvider(SlackCommandProvider):
    """Provider for AWS health check commands."""

    def __init__(self):
        super().__init__(config={"enabled": True})
        self.registry = health_registry


# ============================================================
# REGISTER PROVIDERS WITH AWS ROUTER
# ============================================================

aws_dev_router.register_subcommand(
    name="identitystore",
    provider=IdentityStoreTestProvider(),
    platform="slack",
    description="Test AWS IdentityStore client",
    description_key="dev.aws.services.identitystore.description",
)

aws_dev_router.register_subcommand(
    name="organizations",
    provider=OrganizationsTestProvider(),
    platform="slack",
    description="Test AWS Organizations client",
    description_key="dev.aws.services.organizations.description",
)

aws_dev_router.register_subcommand(
    name="sso",
    provider=SSOAdminTestProvider(),
    platform="slack",
    description="Test AWS SSO Admin client",
    description_key="dev.aws.services.sso_admin.description",
)

aws_dev_router.register_subcommand(
    name="health",
    provider=HealthTestProvider(),
    platform="slack",
    description="AWS integration health check",
    description_key="dev.aws.services.health.description",
)
