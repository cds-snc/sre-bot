"""AWS Client Testing Module - Development commands for testing AWS integrations."""

import structlog

from infrastructure.services import get_slack_provider
from infrastructure.platforms.models import CommandPayload, CommandResponse

logger = structlog.get_logger()


# ============================================================
# PUBLIC: FEATURE REGISTRATION INTERFACE
# ============================================================


def register_slack_features():
    """Explicitly register all AWS dev Slack features with platform provider.

    This is the public entry point for AWS dev feature registration.
    Called by dev.register_dev_subcommands() during startup.
    """
    logger.info("registering_slack_features", module="dev_aws")
    register_aws_dev_subcommands()


def register_aws_dev_subcommands():
    """Register /dev aws subcommands with Slack provider."""
    slack_provider = get_slack_provider()

    logger.info("registering_subcommands", parent_command="dev_aws", count=1)

    # Register: /sre dev aws (using dot notation parent)
    slack_provider.register_command(
        command="aws",
        handler=handle_aws_dev_command,
        description="Test AWS client integrations (identitystore, organizations, sso, health)",
        description_key="dev.subcommands.aws.description",
        parent="sre.dev",
    )


# ============================================================
# COMMAND HANDLERS - Called by platform provider via dispatch_command()
# ============================================================


def handle_aws_dev_command(payload: CommandPayload) -> CommandResponse:
    """Handle /dev aws command."""
    logger.info("command_received", command="aws", text=payload.text)
    return CommandResponse(
        message="AWS dev command - implementation pending",
        ephemeral=True,
    )
