"""Dev Module - Development and testing commands

This module provides development and testing functionality for the Slack app.
Only available in development environment (PREFIX=dev-).
"""

import structlog
from infrastructure.services import get_settings, get_slack_provider
from infrastructure.platforms.models import CommandPayload, CommandResponse
from modules.dev.aws_dev import register_slack_features as register_aws_dev


PREFIX = get_settings().PREFIX
logger = structlog.get_logger()


# ============================================================
# PUBLIC: FEATURE REGISTRATION INTERFACE
# ============================================================


def register_slack_features():
    """Explicitly register all dev module Slack features with platform provider.

    This is the public entry point for dev feature registration.
    Called by sre.register_dev_subcommands() during startup.
    """
    logger.info("registering_slack_features", module="dev")
    register_dev_subcommands()


def register_dev_subcommands():
    """Register /dev subcommands with Slack provider."""
    slack_provider = get_slack_provider()

    logger.info("registering_subcommands", parent_command="dev", count=6)

    # Register: /sre dev google (using dot notation parent)
    slack_provider.register_command(
        command="google",
        handler=handle_google_dev_command,
        description="Google Workspace development commands",
        description_key="dev.subcommands.google.description",
        parent="sre.dev",
    )

    # Register: /sre dev slack
    slack_provider.register_command(
        command="slack",
        handler=handle_slack_dev_command,
        description="Slack development commands",
        description_key="dev.subcommands.slack.description",
        parent="sre.dev",
    )

    # Register: /sre dev stale
    slack_provider.register_command(
        command="stale",
        handler=handle_stale_dev_command,
        description="Test stale channel notification",
        description_key="dev.subcommands.stale.description",
        parent="sre.dev",
    )

    # Register: /sre dev incident
    slack_provider.register_command(
        command="incident",
        handler=handle_incident_dev_command,
        description="List incidents",
        description_key="dev.subcommands.incident.description",
        parent="sre.dev",
    )

    # Register: /sre dev load-incidents
    slack_provider.register_command(
        command="load-incidents",
        handler=handle_load_incidents_command,
        description="Load incidents",
        description_key="dev.subcommands.load_incidents.description",
        parent="sre.dev",
    )

    # Register: /sre dev add-incident
    slack_provider.register_command(
        command="add-incident",
        handler=handle_add_incident_command,
        description="Add incident",
        description_key="dev.subcommands.add_incident.description",
        parent="sre.dev",
    )

    # Register AWS dev commands
    register_aws_dev()


# ============================================================
# COMMAND HANDLERS - Called by platform provider via dispatch_command()
# ============================================================


def handle_google_dev_command(payload: CommandPayload) -> CommandResponse:
    """Handle /dev google command."""
    logger.info("command_received", command="google", text=payload.text)
    return CommandResponse(
        message="Google dev command - implementation pending",
        ephemeral=True,
    )


def handle_slack_dev_command(payload: CommandPayload) -> CommandResponse:
    """Handle /dev slack command."""
    logger.info("command_received", command="slack", text=payload.text)
    return CommandResponse(
        message="Slack dev command - implementation pending",
        ephemeral=True,
    )


def handle_stale_dev_command(payload: CommandPayload) -> CommandResponse:
    """Handle /dev stale command."""
    logger.info("command_received", command="stale")
    return CommandResponse(
        message="Stale channel test - implementation pending",
        ephemeral=True,
    )


def handle_incident_dev_command(payload: CommandPayload) -> CommandResponse:
    """Handle /dev incident command."""
    logger.info("command_received", command="incident")
    return CommandResponse(
        message="Incident list - implementation pending",
        ephemeral=True,
    )


def handle_load_incidents_command(payload: CommandPayload) -> CommandResponse:
    """Handle /dev load-incidents command."""
    logger.info("command_received", command="load-incidents")
    return CommandResponse(
        message="Load incidents - implementation pending",
        ephemeral=True,
    )


def handle_add_incident_command(payload: CommandPayload) -> CommandResponse:
    """Handle /dev add-incident command."""
    logger.info("command_received", command="add-incident")
    return CommandResponse(
        message="Add incident - implementation pending",
        ephemeral=True,
    )
