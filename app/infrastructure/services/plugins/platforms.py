"""Platform command plugin manager."""

from functools import lru_cache
from typing import TYPE_CHECKING

import pluggy
import structlog

from infrastructure import hookspecs
from infrastructure.services.plugins.base import auto_discover_plugins

if TYPE_CHECKING:
    from infrastructure.platforms.providers.slack import SlackPlatformProvider
    from infrastructure.platforms.providers.teams import TeamsPlatformProvider
    from infrastructure.platforms.providers.discord import DiscordPlatformProvider

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def get_platform_plugin_manager() -> pluggy.PluginManager:
    """Get the platform command plugin manager singleton.

    Returns:
        PluginManager configured for platform command registration.
    """
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(hookspecs.platforms)

    logger.info("platform_plugin_manager_created")
    return pm


def discover_and_register_platforms(
    slack_provider: "SlackPlatformProvider | None" = None,
    teams_provider: "TeamsPlatformProvider | None" = None,
    discord_provider: "DiscordPlatformProvider | None" = None,
) -> None:
    """Discover and register platform command plugins."""
    pm = get_platform_plugin_manager()

    # Auto-discover plugins from packages/modules
    # This imports all packages and registers their @hookimpl functions
    auto_discover_plugins(pm, base_paths=["packages", "modules"])

    logger.info("platform_plugins_discovered", plugin_count=len(pm.get_plugins()))

    # Call hooks for each enabled provider
    if slack_provider:
        logger.info("registering_slack_commands")
        pm.hook.register_slack_commands(provider=slack_provider)
        logger.info("slack_commands_registered")

    if teams_provider:
        logger.info("registering_teams_commands")
        pm.hook.register_teams_commands(provider=teams_provider)
        logger.info("teams_commands_registered")

    if discord_provider:
        logger.info("registering_discord_commands")
        pm.hook.register_discord_commands(provider=discord_provider)
        logger.info("discord_commands_registered")
