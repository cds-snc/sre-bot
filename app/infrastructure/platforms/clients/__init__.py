"""Platform clients package.

Provides client facades for platform SDKs and internal communication.

Modules:
    http: Internal HTTP client for localhost endpoint calls
    slack: Slack SDK facade with OperationResult APIs
"""

from infrastructure.platforms.clients.http import InternalHttpClient
from infrastructure.platforms.clients.slack import SlackClientFacade

__all__ = [
    "InternalHttpClient",
    "SlackClientFacade",
]
