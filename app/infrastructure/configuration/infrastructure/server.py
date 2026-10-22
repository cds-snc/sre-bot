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

        backend_url = settings.backend_url
        client_id = settings.google_client_id
        token_expire = settings.access_token_expire_minutes
        ```
    """

    backend_url: str = "http://127.0.0.1:8000"
    notify_ops_channel_id: str = ""
    notify_oncall_group_id: str = ""
    sre_test_channel_id: str = ""
    google_client_id: str | None = None
    google_client_secret: str | None = None
    secret_key: str | None = Field(default=None, alias="SESSION_SECRET_KEY")
    access_token_expire_minutes: int = 30
    access_token_max_age_minutes: int = 1440  # Defaults to 24 hours


class DevSettings(InfrastructureSettings):
    """Development environment configuration.

    Environment Variables:
        SLACK_DEV_MSG_CHANNEL: Slack channel ID for development messages

    Example:
        ```python
        from infrastructure.configuration.infrastructure.server import get_dev_settings

        settings = get_dev_settings()

        dev_channel = settings.slack_dev_msg_channel
        ```
    """

    slack_dev_msg_channel: str = ""


@lru_cache(maxsize=1)
def get_server_settings() -> ServerSettings:
    """Singleton provider for server infrastructure settings."""
    return ServerSettings()


@lru_cache(maxsize=1)
def get_dev_settings() -> DevSettings:
    """Singleton provider for development infrastructure settings."""
    return DevSettings()
