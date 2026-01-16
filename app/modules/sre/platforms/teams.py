"""Teams platform implementation for SRE module - version command.

Uses decorator-based command registration via auto-discovery.
"""

import structlog
from typing import TYPE_CHECKING

from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.services import get_settings

if TYPE_CHECKING:
    from infrastructure.platforms.providers.teams import TeamsPlatformProvider


logger = structlog.get_logger()


def handle_version_command(payload: CommandPayload) -> CommandResponse:
    """Handle @bot sre version Teams command.

    Args:
        payload: Command payload from Teams platform provider

    Returns:
        CommandResponse formatted for Teams
    """
    logger.info("command_received", command="version")

    settings = get_settings()
    return CommandResponse(
        message=f"**SRE Bot version:** {settings.GIT_SHA}",
        ephemeral=True,
    )


def register_commands(provider: "TeamsPlatformProvider") -> None:
    """Register SRE module Teams commands (experimental - no handlers yet).

    Args:
        provider: Teams platform provider instance
    """
    # Teams provider is experimental - command registration available but handlers not implemented yet
    # Uncomment when ready to implement:
    # provider.register_command(
    #     command="version",
    #     handler=handle_version_command,
    #     parent="sre",
    #     description="Show SRE Bot version",
    #     description_key="sre.subcommands.version.description",
    # )
    pass
