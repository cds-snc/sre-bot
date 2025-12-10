"""Server and development infrastructure settings."""

from typing import Any, Dict, Optional

from pydantic import Field, field_validator

from infrastructure.configuration.base import InfrastructureSettings


class ServerSettings(InfrastructureSettings):
    """Server and application runtime configuration.

    Environment Variables:
        BACKEND_URL: Backend API base URL (default: http://127.0.0.1:8000)
        NOTIFY_OPS_CHANNEL_ID: Slack channel ID for ops notifications
        GOOGLE_CLIENT_ID: Google OAuth client ID
        GOOGLE_CLIENT_SECRET: Google OAuth client secret
        SESSION_SECRET_KEY: Secret key for session encryption
        ISSUER_CONFIG: JSON dict of JWT issuer configurations

    Example:
        ```python
        from infrastructure.configuration import settings

        backend_url = settings.server.BACKEND_URL
        client_id = settings.server.GOOGLE_CLIENT_ID
        token_expire = settings.server.ACCESS_TOKEN_EXPIRE_MINUTES
        ```
    """

    BACKEND_URL: str = Field(default="http://127.0.0.1:8000", alias="BACKEND_URL")
    NOTIFY_OPS_CHANNEL_ID: str = Field(default="", alias="NOTIFY_OPS_CHANNEL_ID")
    GOOGLE_CLIENT_ID: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    SECRET_KEY: str | None = Field(default=None, alias="SESSION_SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ACCESS_TOKEN_MAX_AGE_MINUTES: int = 1440  # Defaults to 24 hours
    ISSUER_CONFIG: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        alias="ISSUER_CONFIG",
    )

    @field_validator("ISSUER_CONFIG", mode="before")
    @classmethod
    def validate_issuer_config(cls, v: Optional[Dict[str, Dict[str, Any]]]) -> Any:
        """Validate the ISSUER_CONFIG field."""
        if v is None or not isinstance(v, dict):
            return {}
        return v


class DevSettings(InfrastructureSettings):
    """Development environment configuration.

    Environment Variables:
        SLACK_DEV_MSG_CHANNEL: Slack channel ID for development messages

    Example:
        ```python
        from infrastructure.configuration import settings

        dev_channel = settings.dev.SLACK_DEV_MSG_CHANNEL
        ```
    """

    SLACK_DEV_MSG_CHANNEL: str = Field(default="", alias="SLACK_DEV_MSG_CHANNEL")
