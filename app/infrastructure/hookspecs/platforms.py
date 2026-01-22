"""Hook specifications for platform command registration."""

import pluggy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
