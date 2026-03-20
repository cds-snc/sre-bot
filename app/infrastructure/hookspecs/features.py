"""Hook specifications for feature plugin lifecycle.

Covers the full lifecycle of a feature package:
  - Platform command registration (Slack, Teams, Discord)
  - HTTP route registration
  - Startup settings validation / cache warmup
"""

import pluggy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from structlog.stdlib import BoundLogger
    from infrastructure.platforms.providers.slack import SlackPlatformProvider
    from infrastructure.platforms.providers.teams import TeamsPlatformProvider
    from infrastructure.platforms.providers.discord import DiscordPlatformProvider

hookspec = pluggy.HookspecMarker("sre_bot")


@hookspec
def register_slack_commands(provider: "SlackPlatformProvider") -> None:
    """Register Slack commands with the provider.

    Args:
        provider: Slack provider instance to register commands with.
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
