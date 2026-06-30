"""Slack platform implementation for the SRE module.

Uses decorator-based command registration via auto-discovery.
Registers the SRE subcommands (version, incident, webhooks, groups).
"""

from typing import TYPE_CHECKING, cast

import structlog
from slack_bolt import Ack, Respond

from infrastructure.configuration.app import get_app_settings
from integrations.slack.bootstrap import LegacySlackBootstrap
from integrations.slack.models import CommandPayload, CommandResponse
from modules.incident import incident_helper
from modules.sre import webhook_helper

if TYPE_CHECKING:
    from integrations.slack.provider import SlackPlatformProvider


client = LegacySlackBootstrap().web

logger = structlog.get_logger()


def handle_version_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre version Slack command.

    Args:
        payload: Command payload from Slack platform provider

    Returns:
        CommandResponse formatted for Slack
    """
    logger.info(
        "command_received",
        command="version",
    )

    app_settings = get_app_settings()
    return CommandResponse(
        message=f"🤖 SRE Bot version: {app_settings.GIT_SHA}",
        ephemeral=True,
    )


def handle_incident_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre incident Slack command.

    Bridges the platform provider payload to the legacy incident helper.

    Args:
        payload: Command payload from Slack platform provider

    Returns:
        CommandResponse formatted for Slack
    """
    logger.info(
        "command_received",
        command="incident",
        text=payload.text,
    )

    # Parse command text into args
    args = payload.text.split() if payload.text else []

    # Create legacy body dict expected by incident_helper
    body = {
        "user_id": payload.user_id,
        "channel_id": payload.channel_id,
    }

    # Merge Slack command fields from platform metadata.
    # This keeps legacy handlers compatible with Slack-specific fields.
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

    # Call the legacy incident helper.
    incident_helper.handle_incident_command(
        args=args,
        client=client,
        body=body,
        respond=cast(Respond, capture_respond),
        ack=cast(Ack, noop_ack),
    )

    # Return the captured response.
    if captured_response["blocks"]:
        return CommandResponse(
            message="",
            blocks=captured_response["blocks"],
            ephemeral=True,
        )
    elif captured_response["message"]:
        return CommandResponse(
            message=captured_response["message"],
            ephemeral=True,
        )
    else:
        return CommandResponse(message="Incident command executed", ephemeral=True)


def handle_webhooks_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre webhooks Slack command.

    Bridges the platform provider payload to the legacy webhook helper.

    Args:
        payload: Command payload from Slack platform provider

    Returns:
        CommandResponse formatted for Slack
    """
    logger.info(
        "command_received",
        command="webhooks",
        text=payload.text,
    )

    # Parse command text into args
    args = payload.text.split() if payload.text else []

    # Create legacy body dict expected by webhook_helper
    body = {
        "user_id": payload.user_id,
        "channel_id": payload.channel_id,
    }

    # Merge Slack command fields from platform metadata.
    # This keeps legacy handlers compatible with Slack-specific fields.
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

    # Call the legacy webhook helper.
    webhook_helper.handle_webhook_command(
        args=args,
        client=client,
        body=body,
        respond=cast(Respond, capture_respond),
    )

    # Return captured response
    if captured_response["blocks"]:
        return CommandResponse(
            message="", blocks=captured_response["blocks"], ephemeral=True
        )
    elif captured_response["message"]:
        return CommandResponse(message=captured_response["message"], ephemeral=True)
    else:
        return CommandResponse(
            message="Webhooks command executed",
            ephemeral=True,
        )


def register_commands(provider: "SlackPlatformProvider") -> None:
    """Register SRE module commands with Slack provider.

    Note: No need to register explicit "help" handlers - the platform provider
    automatically generates help when:
    - User types `/sre` (parent command with no handler)
    - User types `/sre help` (explicit help request with legacy_mode=False).
    - User types `/sre <subcommand> help` (subcommand help)

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
