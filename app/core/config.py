"""SRE Bot configuration settings."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """SRE Bot configuration settings."""

    # Environment
    PREFIX: str = ""

    # Slack
    INCIDENT_CHANNEL: str = ""
    SLACK_SECURITY_USER_GROUP_ID: str = ""

    # AWS
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

    # Google Workspace
    INCIDENT_TEMPLATE: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
