"""Hook specifications for feature plugin lifecycle.

Covers the full lifecycle of a feature package:
  - Platform command registration (Slack, Teams, Discord)
  - HTTP route registration
  - Startup settings validation / cache warmup
"""

import pluggy
from typing import TYPE_CHECKING, Callable, Protocol

if TYPE_CHECKING:
    from fastapi import FastAPI
    from structlog.stdlib import BoundLogger
    from infrastructure.events.service import EventDispatcher
    from infrastructure.platforms.providers.slack import SlackPlatformProvider
    from infrastructure.platforms.providers.teams import TeamsPlatformProvider
    from infrastructure.platforms.providers.discord import DiscordPlatformProvider
    from infrastructure.slack.service import SlackBot
    from infrastructure.i18n.resources import I18nResourceRegistry

hookspec = pluggy.HookspecMarker("sre_bot")


class BackgroundJobRegistry(Protocol):
    """Scheduler-agnostic registry for feature background jobs."""

    def register(
        self,
        *,
        job_name: str,
        schedule: str,
        job: Callable[[], None],
    ) -> None:
        """Register a recurring background job by name and schedule."""


@hookspec
def register_slack_commands(provider: "SlackPlatformProvider") -> None:
    """Register Slack commands with the provider.

    Args:
        provider: Slack provider instance to register commands with.
    """


@hookspec
def register_slack_agent_interactions(provider: "SlackBot") -> None:
    """Register Slack agent interactions via the standalone SlackBot service.

    This hookspec supports agent-first interaction registration through the
    standalone SlackBot service while preserving legacy hookspec compatibility.

    Args:
        provider: Standalone SlackBot service used by feature hookimpls.
    """


@hookspec
def register_teams_commands(provider: "TeamsPlatformProvider") -> None:
    """Register Teams commands with the provider.

    Args:
        provider: Teams provider instance to register commands with.
    """


@hookspec
def register_discord_commands(provider: "DiscordPlatformProvider") -> None:
    """Register Discord commands with the provider.

    Args:
        provider: Discord provider instance to register commands with.
    """


@hookspec
def register_routes(app: "FastAPI") -> None:
    """Register HTTP routes with the FastAPI application.

    Called once per feature during startup, after core settings are loaded.
    Implement to call app.include_router(). Omit if the feature has no HTTP
    endpoints.

    Args:
        app: The FastAPI application instance.
    """


@hookspec
def startup_warmup(logger: "BoundLogger") -> None:
    """Validate feature settings and pre-warm caches at startup.

    Called once per feature immediately after register_routes. Implement to
    call the feature's settings provider. A ValidationError raised here aborts
    startup before the application accepts live traffic.

    Omit if all feature settings have safe defaults and lazy validation is
    acceptable.

    Args:
        logger: Structured logger for recording initialization events.
    """


@hookspec
def register_background_job(registry: "BackgroundJobRegistry") -> None:
    """Register recurring feature jobs through the scheduler boundary.

    Called during scheduler initialization at startup. Implementations should
    register deterministic recurring jobs when feature settings require them.

    Args:
        registry: Scheduler-agnostic registry adapter used to register jobs.
    """


@hookspec
def register_i18n_resources(registry: "I18nResourceRegistry") -> None:
    """Register feature translation resource locations.

    Called during plugin discovery to allow features to register their
    translation file locations. This enables co-location of translation YAML
    files with feature packages.

    Implement to call registry.register() with I18nResourceSpec for each
    translation directory your feature provides.

    Omit if the feature has no translations.

    Args:
        registry: I18nResourceRegistry for registering resource specifications.

    Example:
        @hookimpl
        def register_i18n_resources(registry):
            registry.register(
                I18nResourceSpec(
                    owner="packages.geolocate",
                    path="packages/geolocate/locales",
                    required=False,
                    format="yaml",
                    domain="geolocate",
                )
            )
    """


@hookspec
def register_event_handlers(dispatcher: "EventDispatcher") -> None:
    """Register feature event handlers with the application dispatcher.

    Called during feature integration after plugins are discovered.

    Args:
        dispatcher: The application-scoped event dispatcher.
    """
