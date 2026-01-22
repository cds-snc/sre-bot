"""Slack platform implementation for SRE module.

Uses decorator-based command registration via auto-discovery.
Registers all SRE subcommands (version, incident, webhooks, groups).
"""

import structlog
from typing import TYPE_CHECKING, cast

from slack_bolt import Ack, Respond
from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.services import get_settings, get_slack_client
from modules.incident import incident_helper
from modules.sre import webhook_helper

if TYPE_CHECKING:
    from infrastructure.platforms.providers.slack import SlackPlatformProvider


logger = structlog.get_logger()


def handle_version_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre version Slack command.

    Args:
        payload: Command payload from Slack platform provider

    Returns:
        CommandResponse formatted for Slack
    """
    logger.info("command_received", command="version")

    settings = get_settings()
    return CommandResponse(
        message=f"🤖 SRE Bot version: {settings.GIT_SHA}",
        ephemeral=True,
    )


def handle_incident_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre incident Slack command.

    Bridges the new platform provider CommandPayload to the legacy incident_helper interface.

    Args:
        payload: Command payload from Slack platform provider

    Returns:
        CommandResponse formatted for Slack
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

    # Merge all Slack command fields from platform_metadata
    # This ensures legacy handlers have access to all Slack-specific fields
    if payload.platform_metadata:
        body.update(payload.platform_metadata)

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
    """Handle /sre webhooks Slack command.

    Bridges the new platform provider CommandPayload to the legacy webhook_helper interface.

    Args:
        payload: Command payload from Slack platform provider

    Returns:
        CommandResponse formatted for Slack
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

    # Merge all Slack command fields from platform_metadata
    # This ensures legacy handlers have access to all Slack-specific fields
    if payload.platform_metadata:
        body.update(payload.platform_metadata)

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

    # Call legacy webhook helper
    webhook_helper.handle_webhooks_command(
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
        return CommandResponse(message="Webhooks command executed", ephemeral=True)


def handle_groups_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre groups Slack command.

    Args:
        payload: Command payload from Slack platform provider

    Returns:
        CommandResponse formatted for Slack
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


def register_commands(provider: "SlackPlatformProvider") -> None:
    """Register SRE module commands with Slack provider.

    Args:
        provider: Slack platform provider instance
    """
    provider.register_command(
        command="version",
        handler=handle_version_command,
        parent="sre",
        description="Show SRE Bot version",
        description_key="sre.subcommands.version.description",
    )

    provider.register_command(
        command="incident",
        handler=handle_incident_command,
        parent="sre",
        description="Manage incidents",
        description_key="sre.subcommands.incident.description",
        legacy_mode=True,
    )

    provider.register_command(
        command="webhooks",
        handler=handle_webhooks_command,
        parent="sre",
        description="Manage webhooks",
        description_key="sre.subcommands.webhooks.description",
        legacy_mode=True,
    )
