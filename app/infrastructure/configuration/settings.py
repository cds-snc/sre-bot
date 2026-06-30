"""SRE Bot configuration settings - main aggregator."""

from functools import lru_cache
from typing import Any, Callable

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
    get_slack_settings,
    get_aws_settings,
    get_google_workspace_settings,
    get_google_resources_config,
    get_maxmind_settings,
    get_notify_settings,
    get_opsgenie_settings,
    get_sentinel_settings,
    get_trello_settings,
)

# Feature settings
from infrastructure.configuration.features import (
    IncidentFeatureSettings,
    AWSFeatureSettings,
    AtipSettings,
    SreOpsSettings,
    get_incident_settings,
    get_aws_feature_settings,
    get_atip_settings,
    get_sre_ops_settings,
)

# Infrastructure settings
from infrastructure.configuration.infrastructure import (
    IdempotencySettings,
    RetrySettings,
    ServerSettings,
    DevSettings,
    PlatformsSettings,
    DirectorySettings,
    get_server_settings,
    get_dev_settings,
    get_idempotency_settings,
    get_retry_settings,
    get_platforms_settings,
    get_directory_settings,
)

# App-level settings
from infrastructure.configuration.app import get_app_settings


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
        from infrastructure.configuration.app import get_app_settings
        from infrastructure.configuration.infrastructure.retry import get_retry_settings

        app_settings = get_app_settings()
        retry_settings = get_retry_settings()

        # Access infrastructure settings
        if retry_settings.enabled:
            backend = retry_settings.backend
            # Configure retry system...

        # Check environment
        if app_settings.is_production:
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
    feat_incident: IncidentFeatureSettings
    aws_feature: AWSFeatureSettings
    atip: AtipSettings
    sre_ops: SreOpsSettings

    # Infrastructure settings
    server: ServerSettings
    dev: DevSettings
    idempotency: IdempotencySettings
    retry: RetrySettings
    platforms: PlatformsSettings
    directory: DirectorySettings

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production.

        Returns:
            True if PREFIX is empty (production), False otherwise.
        """
        return not bool(self.PREFIX)

    def __init__(self, **kwargs):
        """Initialize Settings by delegating to domain singleton providers.

        Each sub-settings field is sourced from its singleton provider so that
        ``Settings().slack is get_slack_settings()`` holds true.  Callers may
        still pass explicit overrides via kwargs (used in tests).

        Args:
            **kwargs: Optional overrides for specific settings sections.
        """
        # warnings.warn(
        #     "Settings aggregator is deprecated. Use domain-specific providers "
        #     "(e.g., get_slack_settings(), get_server_settings()). "
        #     "See ADR-0055 Standard 4.",
        #     DeprecationWarning,
        #     stacklevel=2,
        # )

        settings_map: dict[str, Callable[[], Any]] = {
            # Integrations
            "slack": get_slack_settings,
            "aws": get_aws_settings,
            "google_workspace": get_google_workspace_settings,
            "maxmind": get_maxmind_settings,
            "notify": get_notify_settings,
            "opsgenie": get_opsgenie_settings,
            "sentinel": get_sentinel_settings,
            "trello": get_trello_settings,
            "google_resources": get_google_resources_config,
            # Features
            "feat_incident": get_incident_settings,
            "aws_feature": get_aws_feature_settings,
            "atip": get_atip_settings,
            "sre_ops": get_sre_ops_settings,
            # Infrastructure
            "server": get_server_settings,
            "dev": get_dev_settings,
            "idempotency": get_idempotency_settings,
            "retry": get_retry_settings,
            "platforms": get_platforms_settings,
            "directory": get_directory_settings,
        }

        for field_name, provider in settings_map.items():
            if field_name not in kwargs:
                kwargs[field_name] = provider()

        # App-level scalar fields default from AppSettings singleton.
        app = get_app_settings()
        kwargs.setdefault("PREFIX", app.PREFIX)
        kwargs.setdefault("LOG_LEVEL", app.LOG_LEVEL)
        kwargs.setdefault("GIT_SHA", app.GIT_SHA)

        super().__init__(**kwargs)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton provider for aggregated Settings.

    Returns:
        Settings instance with all sub-settings sourced from their respective
        singleton providers.
    """
    return Settings()
