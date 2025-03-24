"""SRE Bot configuration settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    SYSTEM_ADMIN_PERMISSIONS: str = Field(
        default="", alias="AWS_SSO_SYSTEM_ADMIN_PERMISSIONS"
    )

    VIEW_ONLY_PERMISSIONS: str = Field(
        default="", alias="AWS_SSO_VIEW_ONLY_PERMISSIONS"
    )
    AWS_REGION: str = Field(default="ca-central-1", alias="AWS_REGION")

    THROTTLING_ERRORS: list[str] = [
        "Throttling",
        "ThrottlingException",
        "RequestLimitExceeded",
    ]
    RESOURCE_NOT_FOUND_ERRORS: list[str] = ["ResourceNotFoundException", "NoSuchEntity"]
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class GoogleWorkspaceSettings(BaseSettings):
    """Google Workspace configuration settings."""

    INCIDENT_TEMPLATE: str = Field(default="", alias="INCIDENT_TEMPLATE")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class Settings(BaseSettings):
    """SRE Bot configuration settings."""

    PREFIX: str = ""
    GIT_SHA: str = "Unknown"

    # Nested settings
    slack: SlackSettings
    aws: AwsSettings
    google_workspace: GoogleWorkspaceSettings

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
        super().__init__(**kwargs)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


# Create the settings instance
settings = Settings()
