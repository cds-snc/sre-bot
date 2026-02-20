"""SRE Module

This module contains the main Slack command handler for `/sre`.
All command routing is handled by the platform provider's route_command() method.
"""

from typing import Any, Dict

import structlog
from slack_bolt import Ack, App, Respond

from infrastructure.platforms.exceptions import ProviderNotFoundError
from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.services import get_platform_service, get_settings

logger = structlog.get_logger()


def register(bot: App) -> None:
    """Register /sre Slack command handler."""
    settings = get_settings()
    bot.command(f"/{settings.PREFIX}sre")(sre_command)


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
    command: Dict[str, Any],
    respond: Respond,
) -> None:
    """Main /sre command handler - delegates to platform provider for routing."""
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
        platform_service = get_platform_service()
        slack_provider = platform_service.get_provider("slack")
    except ProviderNotFoundError as exc:
        logger.error("slack_provider_missing", error=str(exc))
        respond(text="Slack provider is not available.", response_type="ephemeral")
        return

    # Create base payload with all command metadata
    payload = CommandPayload(
        text="",  # Will be set by route_command based on parsed text
        user_id=command.get("user_id", ""),
        user_email=command.get("user_email"),
        channel_id=command.get("channel_id"),
        user_locale=command.get("locale", "en-US"),
        response_url=command.get("response_url"),
        platform_metadata=dict(command),
    )

    # Route hierarchical command through platform provider
    # Converts flat Slack text ("incident help") to hierarchical dispatch ("sre.incident")
    response = slack_provider.route_hierarchical_command(
        root_command="sre",
        text=command.get("text", ""),
        payload=payload,
    )
    _send_response(response, respond)
