"""Discord platform implementation for SRE module - version command.

Uses decorator-based command registration via auto-discovery.
"""

import structlog
from typing import TYPE_CHECKING

from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.services import get_settings

if TYPE_CHECKING:
    from infrastructure.platforms.providers.discord import DiscordPlatformProvider


logger = structlog.get_logger()


def handle_version_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre version Discord command.

    Args:
        payload: Command payload from Discord platform provider

    Returns:
        CommandResponse formatted for Discord
    """
    logger.info("command_received", command="version")

    settings = get_settings()
    return CommandResponse(
        message=f"SRE Bot version: `{settings.GIT_SHA}`",
        ephemeral=True,
    )


def register_commands(provider: "DiscordPlatformProvider") -> None:
    """Register SRE module commands with Discord provider.

    Args:
        provider: Discord platform provider instance
    """
    pass
