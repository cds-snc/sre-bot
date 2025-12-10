"""SRE Bot configuration settings - main aggregator."""

from pydantic_settings import BaseSettings, SettingsConfigDict

# Integration settings
from infrastructure.configuration.integrations import (
    SlackSettings,
    AwsSettings,
    GoogleWorkspaceSettings,
    GoogleResourcesConfig,
    MaxMindSettings,
    NotifySettings,
    OpsGenieSettings,
    SentinelSettings,
    TrelloSettings,
)

# Feature settings
from infrastructure.configuration.features import (
    GroupsFeatureSettings,
    CommandsSettings,
    IncidentFeatureSettings,
    AWSFeatureSettings,
    AtipSettings,
    SreOpsSettings,
)

# Infrastructure settings
from infrastructure.configuration.infrastructure import (
    IdempotencySettings,
    RetrySettings,
    ServerSettings,
    DevSettings,
)


class Settings(BaseSettings):
    """SRE Bot configuration settings - main aggregator.

    Aggregates all domain-specific settings into a single configuration object.
    Settings are organized by concern:

    - **Integrations**: External service configurations (Slack, AWS, Google, etc.)
    - **Features**: Feature module configurations (groups, commands, incident, etc.)
    - **Infrastructure**: Core system configurations (retry, idempotency, server)

    Environment Variables:
        PREFIX: Environment prefix for multi-tenant deployments
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
        GIT_SHA: Git commit SHA for deployment tracking

    Example:
        ```python
        from infrastructure.configuration import settings

        # Access integration settings
        slack_token = settings.slack.SLACK_TOKEN
        aws_region = settings.aws.AWS_REGION

        # Access feature settings
        if settings.groups.circuit_breaker_enabled:
            # Configure circuit breaker...

        # Access infrastructure settings
        if settings.retry.enabled:
            backend = settings.retry.backend
            # Configure retry system...

        # Check environment
        if settings.is_production:
            # Production-specific logic...
        ```
    """

    # Application-level settings
    PREFIX: str = ""
    LOG_LEVEL: str = "INFO"
    GIT_SHA: str = "Unknown"

    # Integration settings
    slack: SlackSettings
    aws: AwsSettings
    google_workspace: GoogleWorkspaceSettings
    maxmind: MaxMindSettings
    notify: NotifySettings
    opsgenie: OpsGenieSettings
    sentinel: SentinelSettings
    trello: TrelloSettings
    google_resources: GoogleResourcesConfig

    # Feature settings
    groups: GroupsFeatureSettings
    commands: CommandsSettings
    feat_incident: IncidentFeatureSettings
    aws_feature: AWSFeatureSettings
    atip: AtipSettings
    sre_ops: SreOpsSettings

    # Infrastructure settings
    server: ServerSettings
    dev: DevSettings
    idempotency: IdempotencySettings
    retry: RetrySettings

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production.

        Returns:
            True if PREFIX is empty (production), False otherwise.
        """
        return not bool(self.PREFIX)

    def __init__(self, **kwargs):
        """Initialize Settings with automatic subsettings instantiation.

        Args:
            **kwargs: Optional overrides for specific settings sections.
        """
        settings_map = {
            # Integrations
            "slack": SlackSettings,
            "aws": AwsSettings,
            "google_workspace": GoogleWorkspaceSettings,
            "maxmind": MaxMindSettings,
            "notify": NotifySettings,
            "opsgenie": OpsGenieSettings,
            "sentinel": SentinelSettings,
            "trello": TrelloSettings,
            "google_resources": GoogleResourcesConfig,
            # Features
            "groups": GroupsFeatureSettings,
            "commands": CommandsSettings,
            "feat_incident": IncidentFeatureSettings,
            "aws_feature": AWSFeatureSettings,
            "atip": AtipSettings,
            "sre_ops": SreOpsSettings,
            # Infrastructure
            "server": ServerSettings,
            "dev": DevSettings,
            "idempotency": IdempotencySettings,
            "retry": RetrySettings,
        }

        for setting_name, setting_class in settings_map.items():
            if setting_name not in kwargs:
                kwargs[setting_name] = setting_class()

        super().__init__(**kwargs)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


# Create the singleton settings instance
settings = Settings()
