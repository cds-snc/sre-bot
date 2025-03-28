"""SRE Bot configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import structlog

logger = structlog.stdlib.get_logger().bind(component="config")


class SlackSettings(BaseSettings):
    """Slack configuration settings."""

    INCIDENT_CHANNEL: str = ""
    SLACK_SECURITY_USER_GROUP_ID: str = ""
    APP_TOKEN: str = ""
    SLACK_TOKEN: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class AwsSettings(BaseSettings):
    """AWS configuration settings."""

    AWS_REGION: str = Field(default="ca-central-1", alias="AWS_REGION")
    SYSTEM_ADMIN_PERMISSIONS: str = Field(
        default="", alias="AWS_SSO_SYSTEM_ADMIN_PERMISSIONS"
    )

    VIEW_ONLY_PERMISSIONS: str = Field(
        default="", alias="AWS_SSO_VIEW_ONLY_PERMISSIONS"
    )
    AUDIT_ROLE_ARN: str = Field(default="", alias="AWS_AUDIT_ACCOUNT_ROLE_ARN")
    ORG_ROLE_ARN: str = Field(default="", alias="AWS_ORG_ACCOUNT_ROLE_ARN")
    LOGGING_ROLE_ARN: str = Field(default="", alias="AWS_LOGGING_ACCOUNT_ROLE_ARN")

    INSTANCE_ID: str = Field(default="", alias="AWS_SSO_INSTANCE_ID")
    INSTANCE_ARN: str = Field(default="", alias="AWS_SSO_INSTANCE_ARN")

    THROTTLING_ERRS: list[str] = [
        "Throttling",
        "ThrottlingException",
        "RequestLimitExceeded",
    ]
    RESOURCE_NOT_FOUND_ERRS: list[str] = ["ResourceNotFoundException", "NoSuchEntity"]
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class GoogleWorkspaceSettings(BaseSettings):
    """Google Workspace configuration settings."""

    GOOGLE_DELEGATED_ADMIN_EMAIL: str = Field(
        default="", alias="GOOGLE_DELEGATED_ADMIN_EMAIL"
    )
    SRE_BOT_EMAIL: str = Field(default="", alias="SRE_BOT_EMAIL")
    GOOGLE_WORKSPACE_CUSTOMER_ID: str = Field(
        default="", alias="GOOGLE_WORKSPACE_CUSTOMER_ID"
    )

    GCP_SRE_SERVICE_ACCOUNT_KEY_FILE: str = Field(
        default="", alias="GCP_SRE_SERVICE_ACCOUNT_KEY_FILE"
    )

    SRE_DRIVE_ID: str = Field(default="", alias="SRE_DRIVE_ID")
    SRE_INCIDENT_FOLDER: str = Field(default="", alias="SRE_INCIDENT_FOLDER")
    INCIDENT_TEMPLATE: str = Field(default="", alias="INCIDENT_TEMPLATE")
    INCIDENT_LIST: str = Field(default="", alias="INCIDENT_LIST")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class MaxMindSettings(BaseSettings):
    """MaxMind configuration settings."""

    MAXMIND_DB_PATH: str = Field(
        default="./geodb/GeoLite2-City.mmdb", alias="MAXMIND_DB_PATH"
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class NotifySettings(BaseSettings):
    """GC Notify configuration settings."""

    NOTIFY_SRE_USER_NAME: str | None = Field(default=None, alias="NOTIFY_SRE_USER_NAME")
    NOTIFY_SRE_CLIENT_SECRET: str | None = Field(
        default=None, alias="NOTIFY_SRE_CLIENT_SECRET"
    )
    NOTIFY_API_URL: str = Field(default="", alias="NOTIFY_API_URL")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class OpsGenieSettings(BaseSettings):
    """OpsGenie configuration settings."""

    OPSGENIE_INTEGRATIONS_KEY: str | None = Field(
        default=None, alias="OPSGENIE_INTEGRATIONS_KEY"
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class SentinelSettings(BaseSettings):
    """Sentinel configuration settings."""

    SENTINEL_CUSTOMER_ID: str | None = Field(default=None, alias="SENTINEL_CUSTOMER_ID")
    SENTINEL_LOG_TYPE: str = Field(default="DevSREBot", alias="SENTINEL_LOG_TYPE")
    SENTINEL_SHARED_KEY: str | None = Field(default=None, alias="SENTINEL_SHARED_KEY")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class TrelloSettings(BaseSettings):
    """Trello configuration settings."""

    TRELLO_APP_KEY: str | None = Field(default=None, alias="TRELLO_APP_KEY")
    TRELLO_TOKEN: str | None = Field(default=None, alias="TRELLO_TOKEN")
    TRELLO_ATIP_BOARD: str | None = Field(default=None, alias="TRELLO_ATIP_BOARD")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class AtipSettings(BaseSettings):
    """ATIP configuration settings."""

    ATIP_ANNOUNCE_CHANNEL: str | None = Field(
        default=None, alias="ATIP_ANNOUNCE_CHANNEL"
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class Settings(BaseSettings):
    """SRE Bot configuration settings."""

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

    # Functionality settings
    atip: AtipSettings

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production."""
        return not bool(self.PREFIX)

    def __init__(self, **kwargs):
        if "slack" not in kwargs:
            kwargs["slack"] = SlackSettings()
        if "aws" not in kwargs:
            kwargs["aws"] = AwsSettings()
        if "google_workspace" not in kwargs:
            kwargs["google_workspace"] = GoogleWorkspaceSettings()
        if "maxmind" not in kwargs:
            kwargs["maxmind"] = MaxMindSettings()
        if "notify" not in kwargs:
            kwargs["notify"] = NotifySettings()
        if "opsgenie" not in kwargs:
            kwargs["opsgenie"] = OpsGenieSettings()
        if "sentinel" not in kwargs:
            kwargs["sentinel"] = SentinelSettings()
        if "trello" not in kwargs:
            kwargs["trello"] = TrelloSettings()
        if "atip" not in kwargs:
            kwargs["atip"] = AtipSettings()
        super().__init__(**kwargs)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


# Create the settings instance
settings = Settings()


def list_configs():
    """List all configuration settings keys"""
    config_settings = {"settings": []}

    for key, value in settings.model_dump().items():
        if isinstance(value, dict):
            config_settings[key] = list(value.keys())
        else:
            config_settings["settings"].append({key: value})

    logger.info(
        "configuration_initialized", config_settings=config_settings["settings"]
    )
    for key, value in config_settings.items():
        if key != "settings":
            logger.info("configuration_loaded", config_setting=key, keys=value)


list_configs()
