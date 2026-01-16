"""Discord platform implementation for SRE module - version command.

Uses decorator-based command registration via auto-discovery.
"""

import structlog

from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.platforms.registry import discord_commands
from infrastructure.services import get_settings


logger = structlog.get_logger()


@discord_commands.register(
    name="version",
    parent="sre",
    description="Show SRE Bot version",
    description_key="sre.subcommands.version.description",
)
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
