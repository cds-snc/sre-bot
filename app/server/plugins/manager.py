"""Feature plugin manager.

One PluginManager for the entire application. Loads the feature plugins
declared as ``pyproject.toml`` entry points and orchestrates their startup
lifecycle via hookspecs.
"""

import importlib.metadata
from collections.abc import Collection
from functools import lru_cache
from typing import TYPE_CHECKING

import pluggy
import structlog

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from contracts.scheduler.registry import BackgroundJobRegistry
from server.plugins.boot import call_hook_per_plugin, load_entry_points, log_plugin_boot_failed
from server.plugins.slack_registrar import PluginSlackRegistrar

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


def installed_plugin_names() -> list[str]:
    """Return the entry-point names declared under ``PLUGIN_NAMESPACE``, without importing any.

    Reads the same distribution metadata pluggy loads from, so the configuration
    phase checks the enablement keys against exactly what ``load_plugins`` would load.
    """
    return sorted(
        {
            entry_point.name
            for distribution in importlib.metadata.distributions()
            for entry_point in distribution.entry_points
            if entry_point.group == PLUGIN_NAMESPACE
        }
    )


def load_plugins(pm: FeaturePluginManager, disabled: Collection[str], logger: BoundLogger) -> None:
    """Register every enabled feature plugin declared under the ``PLUGIN_NAMESPACE`` entry-point group.

    Each disabled name is blocked before loading, so pluggy skips its entry point
    before importing it: a disabled plugin registers nothing and its module never
    runs. A plugin that fails to import is logged as ``plugin_boot_failed`` and stops startup.
    Loading is idempotent, since pluggy skips entry points already registered.

    Args:
        pm: Plugin manager to register the plugins with.
        disabled: Entry-point names the configuration files switch off.
        logger: Structured logger for startup events.

    Raises:
        RuntimeError: The group declares no entry point, which means the project
            metadata is missing or stale. Every plugin disabled is not an error.
    """
    if not installed_plugin_names():
        raise RuntimeError(
            f"no_plugin_entry_points: no entry points in group {PLUGIN_NAMESPACE!r}; run `uv sync` to install the project"
        )
    for blocked in disabled:
        pm.set_blocked(blocked)
    load_entry_points(pm, logger)
    plugins = sorted(name for plugin, _ in pm.list_plugin_distinfo() if (name := pm.get_name(plugin)) is not None)
    logger.info("feature_plugins_loaded", plugins=plugins, disabled=sorted(disabled))


def resolve_plugin_requirements(pm: FeaturePluginManager, logger: BoundLogger) -> None:
    """Fire ``register_requirements`` per plugin, before any registration hook.

    Raises:
        RequiredDependencyError: An enabled plugin requires a dependency that is
            not configured; it is logged as ``plugin_boot_failed`` first.
    """
    call_hook_per_plugin(pm, "register_requirements", logger)
    logger.info("plugin_requirements_resolved")


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
        _register_slack_per_plugin(pm, slack_provider, logger)
        logger.info("slack_commands_registered")

    if event_dispatcher:
        call_hook_per_plugin(pm, "register_event_handlers", logger, dispatcher=event_dispatcher)
        logger.info("event_handlers_registered")

    call_hook_per_plugin(pm, "register_routes", logger, app=app)
    logger.info("feature_routes_registered")

    call_hook_per_plugin(pm, "startup_warmup", logger, logger=logger)
    logger.info("feature_startup_warmup_completed")


def _register_slack_per_plugin(pm: FeaturePluginManager, registrar: SlackCommandRegistrar, logger: BoundLogger) -> None:
    """Call each plugin's ``register_slack_commands`` with a registrar scoped to its entry-point name.

    A blocked (disabled) plugin is listed without a plugin object and is skipped.
    A failure is logged as ``plugin_boot_failed`` and stops startup.
    """
    plugins = [(name, plugin) for name, plugin in pm.list_name_plugin() if plugin is not None]
    for name, plugin in plugins:
        others = [other for _, other in plugins if other is not plugin]
        hook = pm.subset_hook_caller("register_slack_commands", remove_plugins=others)
        try:
            hook(registrar=PluginSlackRegistrar(registrar, name))
        except Exception as error:
            log_plugin_boot_failed(logger, plugin=name, phase="register_slack_commands", error=error)
            raise


def register_background_jobs(registry: BackgroundJobRegistry) -> None:
    """Fire the register_background_jobs hook so features register their recurring jobs.

    Args:
        registry: Scheduler-agnostic registry the scheduler runtime hands to features.
    """
    get_plugin_manager().hook.register_background_jobs(registry=registry)
