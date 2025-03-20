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
    )


class GoogleWorkspaceSettings(BaseSettings):
    """Google Workspace configuration settings."""

    INCIDENT_TEMPLATE: str = Field(default="", alias="INCIDENT_TEMPLATE")


class Settings(BaseSettings):
    """SRE Bot configuration settings."""

    PREFIX: str = ""
    GIT_SHA: str = "Unknown"

    # Nested settings
    slack: SlackSettings = SlackSettings()
    aws: AwsSettings = AwsSettings()
    google_workspace: GoogleWorkspaceSettings = GoogleWorkspaceSettings()

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production."""
        return not bool(self.PREFIX)

    # This is the key configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


# Create the settings instance
settings = Settings()
