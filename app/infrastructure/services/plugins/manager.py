"""Feature plugin manager.

One PluginManager for the entire application. Handles discovery of all feature
packages and orchestrates their full startup lifecycle via hookspecs.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

import pluggy
import structlog

from infrastructure import hookspecs
from infrastructure.services.plugins.base import auto_discover_plugins

if TYPE_CHECKING:
    from fastapi import FastAPI
    from structlog.stdlib import BoundLogger
    from infrastructure.platforms.providers.slack import SlackPlatformProvider
    from infrastructure.platforms.providers.teams import TeamsPlatformProvider
    from infrastructure.platforms.providers.discord import DiscordPlatformProvider

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def get_plugin_manager() -> pluggy.PluginManager:
    """Get the application-scoped feature plugin manager singleton.

    Returns:
        PluginManager configured with all feature lifecycle hookspecs.
    """
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(hookspecs.features)

    logger.info("plugin_manager_created")
    return pm


def discover_and_init_features(
    app: "FastAPI",
    logger: "BoundLogger",
    slack_provider: "SlackPlatformProvider | None" = None,
    teams_provider: "TeamsPlatformProvider | None" = None,
    discord_provider: "DiscordPlatformProvider | None" = None,
) -> None:
    """Discover all feature packages and run their full startup lifecycle.

    Lifecycle order (matches hookspec invocation order):
      1. Discovery  — import every package under packages/ and modules/
      2. Commands   — register Slack/Teams/Discord commands per enabled provider
      3. Routes     — each feature calls app.include_router() via register_routes
      4. Warmup     — each feature validates its settings via startup_warmup

    Args:
        app: FastAPI application instance passed to register_routes hookimpls.
        logger: Structured logger passed to startup_warmup hookimpls.
        slack_provider: Slack provider, if initialized.
        teams_provider: Teams provider, if initialized.
        discord_provider: Discord provider, if initialized.
    """
    pm = get_plugin_manager()

    auto_discover_plugins(pm, base_paths=["packages", "modules"])
    logger.info("feature_plugins_discovered", plugin_count=len(pm.get_plugins()))

    # Platform commands — conditional on which providers are active
    if slack_provider:
        pm.hook.register_slack_commands(provider=slack_provider)
        logger.info("slack_commands_registered")

    if teams_provider:
        pm.hook.register_teams_commands(provider=teams_provider)
        logger.info("teams_commands_registered")

    if discord_provider:
        pm.hook.register_discord_commands(provider=discord_provider)
        logger.info("discord_commands_registered")

    # HTTP routes — all features self-register
    pm.hook.register_routes(app=app)
    logger.info("feature_routes_registered")

    # Settings warmup — features with required env vars validate here
    pm.hook.startup_warmup(logger=logger)
    logger.info("feature_startup_warmup_completed")
