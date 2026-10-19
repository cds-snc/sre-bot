"""Integration settings __init__ - exports the integration settings still homed here."""

from infrastructure.configuration.integrations.google import (
    GoogleResourcesConfig,
    GoogleWorkspaceSettings,
    get_google_resources_config,
    get_google_workspace_settings,
)
from infrastructure.configuration.integrations.slack import (
    SlackSettings,
    get_slack_settings,
)

__all__ = [
    "SlackSettings",
    "GoogleWorkspaceSettings",
    "GoogleResourcesConfig",
    "get_slack_settings",
    "get_google_workspace_settings",
    "get_google_resources_config",
]
