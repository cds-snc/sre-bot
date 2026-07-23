"""SRE module.

This module contains the main Slack command handler for `/sre`.
All command routing is handled by the platform provider's route_command()
method.
"""

from typing import Any

import structlog
from slack_bolt import Ack, App, Respond

from infrastructure.slack.settings import get_slack_transport_settings
from integrations.slack.models import CommandPayload, CommandResponse
from integrations.slack.provider import get_slack_provider

logger = structlog.get_logger()


def register(bot: App) -> None:
    """Register /sre Slack command handler."""
    transport_settings = get_slack_transport_settings()
    bot.command(f"/{transport_settings.COMMAND_PREFIX}sre")(sre_command)


def _send_response(response: CommandResponse, respond: Respond) -> None:
    response_type = "ephemeral" if response.ephemeral else "in_channel"
    if response.blocks:
        respond(
            text=response.message or "",
            blocks=response.blocks,
            response_type=response_type,
        )
        return
    if response.attachments:
        respond(
            text=response.message or "",
            attachments=response.attachments,
            response_type=response_type,
        )
        return
    if response.message:
        respond(text=response.message, response_type=response_type)
        return
    respond(text="", response_type=response_type)


def sre_command(
    ack: Ack,
    command: dict[str, Any],
    respond: Respond,
) -> None:
    """Main /sre command handler that delegates to the platform provider."""
    ack()
    logger.info(
        "sre_command_received",
        command=command.get("text", ""),
        user_id=command.get("user_id"),
        user_name=command.get("user_name"),
        channel_id=command.get("channel_id"),
        channel_name=command.get("channel_name"),
    )

    try:
        slack_provider = get_slack_provider()
    except Exception as exc:
        logger.error("slack_provider_missing", error=str(exc))
        respond(
            text="Slack provider is not available.",
            response_type="ephemeral",
        )
        return

    # Create base payload with all command metadata
    payload = CommandPayload(
        text="",
        user_id=command.get("user_id", ""),
        user_email=command.get("user_email"),
        channel_id=command.get("channel_id"),
        user_locale=command.get("locale", "en-US"),
        response_url=command.get("response_url"),
        platform_metadata=dict(command),
    )

    # Route hierarchical command through the platform provider.
    # Converts flat Slack text ("incident help") to hierarchical dispatch.
    response = slack_provider.route_hierarchical_command(
        root_command="sre",
        text=command.get("text", ""),
        payload=payload,
    )
    _send_response(response, respond)
