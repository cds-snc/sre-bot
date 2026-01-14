"""Platform clients package.

Provides client facades for platform SDKs and internal communication.

Modules:
    http: Internal HTTP client for localhost endpoint calls
    slack: Slack SDK facade with OperationResult APIs
    teams: Microsoft Teams Bot Framework facade
    discord: Discord SDK facade (placeholder)
"""

from infrastructure.platforms.clients.http import InternalHttpClient
from infrastructure.platforms.clients.slack import SlackClientFacade
from infrastructure.platforms.clients.teams import TeamsClientFacade
from infrastructure.platforms.clients.discord import DiscordClientFacade

__all__ = [
    "InternalHttpClient",
    "SlackClientFacade",
    "TeamsClientFacade",
    "DiscordClientFacade",
]
