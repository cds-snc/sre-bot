"""Feature plugin manager.

One PluginManager for the entire application. Loads the feature plugins
declared as ``pyproject.toml`` entry points and orchestrates their startup
lifecycle via hookspecs.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

import pluggy
import structlog

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from contracts.scheduler.registry import BackgroundJobRegistry

if TYPE_CHECKING:
    from fastapi import FastAPI
    from structlog.stdlib import BoundLogger

    from contracts.slack.registrar import SlackCommandRegistrar
    from infrastructure.events.service import EventDispatcher

logger = structlog.get_logger()

type FeaturePluginManager = pluggy.PluginManager


@lru_cache(maxsize=1)
def get_plugin_manager() -> FeaturePluginManager:
    """Get the application-scoped feature plugin manager singleton.

    Returns:
        PluginManager configured with all feature lifecycle hookspecs.
    """
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)

    logger.info("plugin_manager_created")
    return pm


def load_plugins(pm: FeaturePluginManager, logger: BoundLogger) -> None:
    """Register every feature plugin declared under the ``PLUGIN_NAMESPACE`` entry-point group.

    Errors are not caught: a plugin that fails to import stops startup. Loading
    is idempotent, since pluggy skips entry points already registered.

    Args:
        pm: Plugin manager to register the plugins with.
        logger: Structured logger for startup events.

    Raises:
        RuntimeError: No plugin is registered from the group, which means the
            project metadata is missing or stale.
    """
    pm.load_setuptools_entrypoints(PLUGIN_NAMESPACE)
    plugins = sorted(name for plugin, _ in pm.list_plugin_distinfo() if (name := pm.get_name(plugin)) is not None)
    if not plugins:
        raise RuntimeError(
            f"no_plugins_loaded: no entry points in group {PLUGIN_NAMESPACE!r}; run `uv sync` to install the project"
        )
    logger.info("feature_plugins_loaded", plugins=plugins)


def register_feature_integrations(
    app: FastAPI,
    logger: BoundLogger,
    slack_provider: SlackCommandRegistrar | None = None,
    event_dispatcher: EventDispatcher | None = None,
) -> None:
    """Phase 2 — Register commands, routes, and run startup warmup.

    Must be called AFTER the translation service is initialized and injected
    into platform providers so that command help-text translation works at
    registration time.

    Args:
        app: FastAPI application instance passed to register_routes hookimpls.
        logger: Structured logger passed to startup_warmup hookimpls.
        slack_provider: Slack command registrar (the platform provider), if initialized.
    """
    pm = get_plugin_manager()

    if slack_provider:
        pm.hook.register_slack_commands(registrar=slack_provider)
        logger.info("slack_commands_registered")

    if event_dispatcher:
        pm.hook.register_event_handlers(dispatcher=event_dispatcher)
        logger.info("event_handlers_registered")

    pm.hook.register_routes(app=app)
    logger.info("feature_routes_registered")

    pm.hook.startup_warmup(logger=logger)
    logger.info("feature_startup_warmup_completed")


def register_background_jobs(registry: BackgroundJobRegistry) -> None:
    """Fire the register_background_jobs hook so features register their recurring jobs.

    Args:
        registry: Scheduler-agnostic registry the scheduler runtime hands to features.
    """
    get_plugin_manager().hook.register_background_jobs(registry=registry)
