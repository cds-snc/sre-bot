"""SRE module - Platform command registration."""

from infrastructure.services import hookimpl
from modules.sre.platforms import slack, teams, discord


@hookimpl
def register_slack_commands(provider):
    """Register SRE module Slack commands."""
    slack.register_commands(provider)


@hookimpl
def register_teams_commands(provider):
    """Register SRE module Teams commands."""
    teams.register_commands(provider)


@hookimpl
def register_discord_commands(provider):
    """Register SRE module Discord commands."""
    discord.register_commands(provider)
