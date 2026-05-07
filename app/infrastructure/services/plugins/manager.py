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
from infrastructure.i18n.resources import I18nResourceRegistry

if TYPE_CHECKING:
    from fastapi import FastAPI
    from structlog.stdlib import BoundLogger
    from infrastructure.events.service import EventDispatcher
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


def collect_feature_i18n_resources(
    logger: "BoundLogger",
) -> I18nResourceRegistry:
    """Phase 1 — Discover plugins and collect i18n resource registrations.

    Must be called BEFORE translation service initialization so that all
    feature-package locale paths are known and included in the loaded catalogs.

    Args:
        logger: Structured logger for startup events.

    Returns:
        I18nResourceRegistry with every registered translation resource.
    """
    pm = get_plugin_manager()

    auto_discover_plugins(pm, base_paths=["packages", "modules"])
    logger.info("feature_plugins_discovered", plugin_count=len(pm.get_plugins()))

    i18n_registry = I18nResourceRegistry()
    pm.hook.register_i18n_resources(registry=i18n_registry)
    logger.info(
        "i18n_resources_collected", resource_count=i18n_registry.get_resource_count()
    )

    return i18n_registry


def register_feature_integrations(
    app: "FastAPI",
    logger: "BoundLogger",
    slack_provider: "SlackPlatformProvider | None" = None,
    teams_provider: "TeamsPlatformProvider | None" = None,
    discord_provider: "DiscordPlatformProvider | None" = None,
    event_dispatcher: "EventDispatcher | None" = None,
) -> None:
    """Phase 2 — Register commands, routes, and run startup warmup.

    Must be called AFTER the translation service is initialized and injected
    into platform providers so that command help-text translation works at
    registration time.

    Args:
        app: FastAPI application instance passed to register_routes hookimpls.
        logger: Structured logger passed to startup_warmup hookimpls.
        slack_provider: Slack provider, if initialized.
        teams_provider: Teams provider, if initialized.
        discord_provider: Discord provider, if initialized.
    """
    pm = get_plugin_manager()

    if slack_provider:
        pm.hook.register_slack_interactions(provider=slack_provider)
        logger.info("slack_interactions_registered")

    if teams_provider:
        pm.hook.register_teams_interactions(provider=teams_provider)
        logger.info("teams_interactions_registered")

    if discord_provider:
        pm.hook.register_discord_interactions(provider=discord_provider)
        logger.info("discord_interactions_registered")

    if event_dispatcher:
        pm.hook.register_event_handlers(dispatcher=event_dispatcher)
        logger.info("event_handlers_registered")

    pm.hook.register_routes(app=app)
    logger.info("feature_routes_registered")

    pm.hook.startup_warmup(logger=logger)
    logger.info("feature_startup_warmup_completed")


def discover_and_init_features(
    app: "FastAPI",
    logger: "BoundLogger",
    slack_provider: "SlackPlatformProvider | None" = None,
    teams_provider: "TeamsPlatformProvider | None" = None,
    discord_provider: "DiscordPlatformProvider | None" = None,
    event_dispatcher: "EventDispatcher | None" = None,
) -> I18nResourceRegistry:
    """Discover all feature packages and run their full startup lifecycle.

    Kept for backward compatibility with tests. For production startup use
    collect_feature_i18n_resources() + register_feature_integrations() with
    translation service initialization between the two phases.

    Returns:
        I18nResourceRegistry containing all registered translation resources.
    """
    i18n_registry = collect_feature_i18n_resources(logger=logger)
    register_feature_integrations(
        app=app,
        logger=logger,
        slack_provider=slack_provider,
        teams_provider=teams_provider,
        discord_provider=discord_provider,
        event_dispatcher=event_dispatcher,
    )
    return i18n_registry
