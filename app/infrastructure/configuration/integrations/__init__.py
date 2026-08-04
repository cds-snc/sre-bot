"""Integration settings __init__ - exports all integration settings."""

from infrastructure.configuration.integrations.aws import AwsSettings, get_aws_settings
from infrastructure.configuration.integrations.google import (
    GoogleResourcesConfig,
    GoogleWorkspaceSettings,
    get_google_resources_config,
    get_google_workspace_settings,
)
from infrastructure.configuration.integrations.maxmind import (
    MaxMindSettings,
    get_maxmind_settings,
)
from infrastructure.configuration.integrations.notify import (
    NotifySettings,
    get_notify_settings,
)
from infrastructure.configuration.integrations.opsgenie import (
    OpsGenieSettings,
    get_opsgenie_settings,
)
from infrastructure.configuration.integrations.sentinel import (
    SentinelSettings,
    get_sentinel_settings,
)
from infrastructure.configuration.integrations.slack import (
    SlackSettings,
    get_slack_settings,
)
from infrastructure.configuration.integrations.trello import (
    TrelloSettings,
    get_trello_settings,
)

__all__ = [
    "SlackSettings",
    "AwsSettings",
    "GoogleWorkspaceSettings",
    "GoogleResourcesConfig",
    "MaxMindSettings",
    "NotifySettings",
    "OpsGenieSettings",
    "SentinelSettings",
    "TrelloSettings",
    "get_slack_settings",
    "get_aws_settings",
    "get_google_workspace_settings",
    "get_google_resources_config",
    "get_maxmind_settings",
    "get_notify_settings",
    "get_opsgenie_settings",
    "get_sentinel_settings",
    "get_trello_settings",
]
