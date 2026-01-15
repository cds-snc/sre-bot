"""SRE Module - Main command handler for /sre commands

This module provides the entry point for all /sre commands and subcommands.
It bridges the legacy Slack Bolt interface with the new platform provider system.
"""

import structlog
from typing import cast
from slack_bolt import Ack, App, Respond
from slack_sdk import WebClient

from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.services import (
    get_slack_provider,
    get_settings,
    get_slack_client,
)
from packages.geolocate.slack import register_slack_commands as register_geolocate
from modules.incident import incident_helper
from modules.sre import webhook_helper
from modules.dev.core import register_slack_features as register_dev

logger = structlog.get_logger()


# ============================================================
# PUBLIC: FEATURE REGISTRATION INTERFACE
# ============================================================


def register_slack_features():
    """Register all /sre features with the Slack platform provider.

    This is the public entry point called by main.py during startup.
    Registers all subcommands with parent="sre" for hierarchical structure.
    """
    logger.info("registering_slack_features", module="sre")

    # Register all subcommands (each will use parent="sre")
    _register_geolocate_subcommand()
    _register_incident_subcommand()
    _register_webhooks_subcommand()
    _register_groups_subcommand()
    _register_version_subcommand()
    _register_dev_subcommands()


def _register_geolocate_subcommand():
    """Register geolocate package subcommand.

    ✅ CORRECT PATTERN: Geolocate package owns its registration.
    Eventually all features should follow this pattern.
    """
    try:
        register_geolocate()
        logger.info("subcommand_registered", command="geolocate")
    except Exception as e:
        logger.warning(
            "subcommand_registration_failed", command="geolocate", error=str(e)
        )


def _register_incident_subcommand():
    """Register incident management subcommand.

    TODO: Move handler to modules/incident/ with its own register_slack_features().
    Handler should live with the feature code, not here.
    """
    slack_provider = get_slack_provider()
    slack_provider.register_command(
        command="incident",
        handler=handle_incident_command,
        description="Manage incidents",
        description_key="sre.subcommands.incident.description",
        parent="sre",
    )
    logger.info("subcommand_registered", command="incident")


def _register_webhooks_subcommand():
    """Register webhooks management subcommand.

    TODO: Move handler to modules/sre/webhooks/ with its own register_slack_features().
    Handler should live with the feature code, not here.
    """
    slack_provider = get_slack_provider()
    slack_provider.register_command(
        command="webhooks",
        handler=handle_webhooks_command,
        description="Manage webhooks",
        description_key="sre.subcommands.webhooks.description",
        parent="sre",
    )
    logger.info("subcommand_registered", command="webhooks")


def _register_groups_subcommand():
    """Register groups management subcommand.

    TODO: Integrate with modules/groups/ existing command registry.
    Groups module already has architecture, needs platform provider integration.
    """
    slack_provider = get_slack_provider()
    slack_provider.register_command(
        command="groups",
        handler=handle_groups_command,
        description="Manage groups and memberships",
        description_key="sre.subcommands.groups.description",
        parent="sre",
    )
    logger.info("subcommand_registered", command="groups")


def _register_version_subcommand():
    """Register version info subcommand.

    Note: Version is SRE-level metadata, reasonable to keep here.
    """
    slack_provider = get_slack_provider()
    slack_provider.register_command(
        command="version",
        handler=handle_version_command,
        description="Show SRE Bot version",
        description_key="sre.subcommands.version.description",
        parent="sre",
    )
    logger.info("subcommand_registered", command="version")


def _register_dev_subcommands():
    """Register dev module subcommands.

    ✅ CORRECT PATTERN: Dev module owns its registration.
    Eventually all features should follow this pattern.
    """
    try:
        register_dev()
        logger.info("subcommand_registered", command="dev")
    except Exception as e:
        logger.warning("subcommand_registration_failed", command="dev", error=str(e))


# ============================================================
# COMMAND HANDLERS - Called by platform provider via dispatch_command()
# ============================================================


def handle_groups_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre groups command.

    Args:
        payload: Command payload from Slack platform provider

    Returns:
        Response to send to Slack
    """
    logger.info("command_received", command="groups", text=payload.text)

    # Groups module uses the new architecture with its own command registry
    # For now, direct users to use the full groups interface
    # TODO: Migrate groups module to use platform providers instead of legacy commands
    return CommandResponse(
        message=(
            "Groups management is available through the comprehensive groups interface.\n"
            "For now, please use the legacy command structure or API endpoints.\n"
            "Full platform migration coming soon."
        ),
        ephemeral=True,
    )


def handle_incident_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre incident command.

    Bridges the new platform provider CommandPayload to the legacy incident_helper interface.

    Args:
        payload: Command payload from Slack platform provider

    Returns:
        Response to send to Slack
    """
    logger.info("command_received", command="incident", text=payload.text)

    # Get Slack client singleton
    slack_facade = get_slack_client()
    client = slack_facade.raw_client

    # Parse command text into args
    args = payload.text.split() if payload.text else []

    # Create legacy body dict expected by incident_helper
    body = {
        "user_id": payload.user_id,
        "channel_id": payload.channel_id,
    }

    # Capture responses sent via respond()
    captured_response = {"message": None, "blocks": None}

    def capture_respond(text=None, blocks=None):
        """Capture response from legacy respond() calls."""
        if blocks:
            captured_response["blocks"] = blocks
        elif text:
            captured_response["message"] = text

    def noop_ack():
        """No-op ack - already handled by platform provider."""
        pass

    # Call legacy incident helper
    # Note: Using cast for bridge compatibility between platform-agnostic and Slack-specific interfaces
    incident_helper.handle_incident_command(
        args=args,
        client=client,
        body=body,
        respond=cast(Respond, capture_respond),
        ack=cast(Ack, noop_ack),
    )

    # Return captured response
    if captured_response["blocks"]:
        return CommandResponse(blocks=captured_response["blocks"], ephemeral=True)
    elif captured_response["message"]:
        return CommandResponse(message=captured_response["message"], ephemeral=True)
    else:
        return CommandResponse(message="Incident command executed", ephemeral=True)


def handle_webhooks_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre webhooks command.

    Bridges the new platform provider CommandPayload to the legacy webhook_helper interface.

    Args:
        payload: Command payload from Slack platform provider

    Returns:
        Response to send to Slack
    """
    logger.info("command_received", command="webhooks", text=payload.text)

    # Get Slack client singleton
    slack_facade = get_slack_client()
    client = slack_facade.raw_client

    # Parse command text into args
    args = payload.text.split() if payload.text else []

    # Create legacy body dict expected by webhook_helper
    body = {
        "user_id": payload.user_id,
        "channel_id": payload.channel_id,
    }

    # Capture responses sent via respond()
    captured_response = {"message": None, "blocks": None}

    def capture_respond(text=None, blocks=None):
        """Capture response from legacy respond() calls."""
        if blocks:
            captured_response["blocks"] = blocks
        elif text:
            captured_response["message"] = text

    # Call legacy webhook helper
    # Note: Using cast for bridge compatibility between platform-agnostic and Slack-specific interfaces
    webhook_helper.handle_webhook_command(
        args=args,
        client=client,
        body=body,
        respond=cast(Respond, capture_respond),
    )

    # Return captured response
    if captured_response["blocks"]:
        return CommandResponse(blocks=captured_response["blocks"], ephemeral=True)
    elif captured_response["message"]:
        return CommandResponse(message=captured_response["message"], ephemeral=True)
    else:
        return CommandResponse(message="Webhooks command executed", ephemeral=True)


def handle_version_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre version command."""
    logger.info("command_received", command="version")

    settings = get_settings()
    return CommandResponse(
        message=f"SRE Bot version: {settings.GIT_SHA}",
        ephemeral=True,
    )


# ============================================================
# SLACK BOT INTEGRATION - Legacy Bolt interface
# ============================================================


def register(bot: App):
    """Register the /sre Slack command with Bolt.

    Called by main.py to register the command handler with Slack Bolt.
    This provides the legacy Bolt entry point that dispatches to platform providers.
    """
    settings = get_settings()
    bot.command(f"/{settings.PREFIX}sre")(sre_command)


def sre_command(ack: Ack, command, respond: Respond, client: WebClient):
    """Handle /sre command from Slack Bolt.

    This is the legacy Bolt entry point that bridges to the platform provider system.
    It acknowledges the command, extracts the subcommand, and dispatches to the
    appropriate handler via the platform provider.

    Args:
        ack: Slack Bolt acknowledgment function
        command: Command payload from Slack
        respond: Function to send response back to Slack
        client: Slack WebClient instance
    """
    ack()

    text = command.get("text", "").strip()
    user_id = command.get("user_id", "")
    channel_id = command.get("channel_id", "")

    logger.info("sre_command_received", text=text, user=user_id, channel=channel_id)

    # Get platform service
    slack_provider = get_slack_provider()

    if not slack_provider:
        respond("Slack provider not available")
        return

    # Handle help request
    if not text or text.lower() in ("help", "aide", "--help", "-h"):
        # Show all commands under /sre (root_command="sre")
        help_text = slack_provider.generate_help(root_command="sre")
        respond(help_text)
        return

    # Parse subcommand and args
    parts = text.split(maxsplit=1)
    subcommand = parts[0]
    subcommand_args = parts[1] if len(parts) > 1 else ""

    # Create CommandPayload
    payload = CommandPayload(
        text=subcommand_args,
        user_id=user_id,
        channel_id=channel_id,
        user_email="",
        response_url="",
    )

    # Dispatch to handler
    try:
        # Build full_path: subcommand in /sre context -> "sre.{subcommand}"
        full_command_path = f"sre.{subcommand}"
        response = slack_provider.dispatch_command(full_command_path, payload)

        if response.blocks:
            respond(blocks=response.blocks)
        elif response.message:
            respond(response.message)
        else:
            respond(f"Executed: {subcommand}")

    except Exception as e:
        logger.error("command_dispatch_failed", subcommand=subcommand, error=str(e))
        respond(f"Error executing command '{subcommand}': {str(e)}")
