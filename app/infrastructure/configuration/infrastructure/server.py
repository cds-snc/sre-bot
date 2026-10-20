"""Server and development infrastructure settings."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class ServerSettings(InfrastructureSettings):
    """Server and application runtime configuration.

    Environment Variables:
        BACKEND_URL: Backend API base URL (default: http://127.0.0.1:8000)
        NOTIFY_OPS_CHANNEL_ID: Slack channel ID for ops notifications
        NOTIFY_ONCALL_GROUP_ID: Slack user-group ID for Notify on-call mentions
        GOOGLE_CLIENT_ID: Google OAuth client ID
        GOOGLE_CLIENT_SECRET: Google OAuth client secret
        SESSION_SECRET_KEY: Secret key for session encryption

    Example:
        ```python
        from infrastructure.configuration.infrastructure.server import get_server_settings

        settings = get_server_settings()

        backend_url = settings.BACKEND_URL
        client_id = settings.GOOGLE_CLIENT_ID
        token_expire = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        ```
    """

    BACKEND_URL: str = Field(default="http://127.0.0.1:8000", alias="BACKEND_URL")
    NOTIFY_OPS_CHANNEL_ID: str = Field(default="", alias="NOTIFY_OPS_CHANNEL_ID")
    NOTIFY_ONCALL_GROUP_ID: str = Field(default="", alias="NOTIFY_ONCALL_GROUP_ID")
    SRE_TEST_CHANNEL_ID: str = Field(default="", alias="SRE_TEST_CHANNEL_ID")
    GOOGLE_CLIENT_ID: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    SECRET_KEY: str | None = Field(default=None, alias="SESSION_SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ACCESS_TOKEN_MAX_AGE_MINUTES: int = 1440  # Defaults to 24 hours


class DevSettings(InfrastructureSettings):
    """Development environment configuration.

    Environment Variables:
        SLACK_DEV_MSG_CHANNEL: Slack channel ID for development messages

    Example:
        ```python
        from infrastructure.configuration.infrastructure.server import get_dev_settings

        settings = get_dev_settings()

        dev_channel = settings.SLACK_DEV_MSG_CHANNEL
        ```
    """

    SLACK_DEV_MSG_CHANNEL: str = Field(default="", alias="SLACK_DEV_MSG_CHANNEL")


@lru_cache(maxsize=1)
def get_server_settings() -> ServerSettings:
    """Singleton provider for server infrastructure settings."""
    return ServerSettings()


@lru_cache(maxsize=1)
def get_dev_settings() -> DevSettings:
    """Singleton provider for development infrastructure settings."""
    return DevSettings()
