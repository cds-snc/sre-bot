"""Vendor settings for Slack runtime credentials and delivery mode.

Exposes `SlackSettings` and the cached `get_slack_settings()` provider.

Validation behavior mirrors Slack delivery mode requirements:
- HTTP Events mode (`SLACK_SOCKET_MODE=false`) fails fast at boot when
    `SLACK_SIGNING_SECRET` is missing.
- Socket Mode logs an informational notice when `SLACK_SIGNING_SECRET` is not
    set, because Socket Mode request authenticity is handled by the connection
    handshake rather than HTTP request-signature verification.

Vendor credentials and transport settings only (tokens, secrets, per-call
timeout, retry budget, delivery mode, error-code catalogues). Feature-domain
configuration (channel IDs, user-group IDs) lives with the consuming feature.
"""

from functools import lru_cache

import structlog
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)


class SlackSettings(BaseSettings):
    """Vendor credential, transport, and classification settings for Slack."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    ENABLED: bool = Field(default=False, alias="SLACK_ENABLED")
    SOCKET_MODE: bool = Field(default=True, alias="SLACK_SOCKET_MODE")

    BOT_TOKEN: str = Field(default="", alias="SLACK_BOT_TOKEN")
    USER_TOKEN: str = Field(default="", alias="SLACK_USER_TOKEN", repr=False)
    APP_TOKEN: str | None = Field(default=None, alias="SLACK_APP_TOKEN")
    SIGNING_SECRET: str | None = Field(default=None, alias="SLACK_SIGNING_SECRET")

    REQUEST_TIMEOUT_SECONDS: int = Field(default=10, alias="SLACK_REQUEST_TIMEOUT_SECONDS")
    RETRY_MAX_ATTEMPTS: int = Field(default=2, alias="SLACK_RETRY_MAX_ATTEMPTS")
    TRANSIENT_RETRY_AFTER_SECONDS: int = Field(
        default=30,
        alias="SLACK_TRANSIENT_RETRY_AFTER_SECONDS",
        description="Retry hint attached to transient classifications when Slack sends no Retry-After header, in seconds.",
    )

    UNAUTHORIZED_ERRORS: list[str] = Field(
        default=[
            "not_authed",
            "invalid_auth",
            "account_inactive",
            "token_revoked",
            "token_expired",
            "missing_scope",
            "no_permission",
            "not_allowed_token_type",
            "access_denied",
            "permission_denied",
            "ekm_access_denied",
            "team_access_not_granted",
        ],
        alias="SLACK_UNAUTHORIZED_ERRORS",
        description="Slack Web API error codes classified as UNAUTHORIZED.",
    )
    NOT_FOUND_ERRORS: list[str] = Field(
        default=["channel_not_found", "user_not_found", "users_not_found", "message_not_found", "no_such_subteam"],
        alias="SLACK_NOT_FOUND_ERRORS",
        description="Slack Web API error codes classified as NOT_FOUND.",
    )
    TRANSIENT_ERRORS: list[str] = Field(
        default=["ratelimited", "internal_error", "fatal_error", "service_unavailable", "request_timeout"],
        alias="SLACK_TRANSIENT_ERRORS",
        description="Slack Web API error codes classified as TRANSIENT_ERROR.",
    )

    @model_validator(mode="after")
    def _validate_transport_credentials(self) -> SlackSettings:
        if not self.ENABLED:
            return self
        if self.SOCKET_MODE and not self.APP_TOKEN:
            raise ValueError("SLACK_APP_TOKEN is required when SLACK_SOCKET_MODE=true and SLACK_ENABLED=true")
        if not self.SOCKET_MODE and not self.SIGNING_SECRET:
            raise ValueError("SLACK_SIGNING_SECRET is required when SLACK_SOCKET_MODE=false and SLACK_ENABLED=true")
        if self.SOCKET_MODE and not self.SIGNING_SECRET:
            logger.info(
                "slack_signing_secret_not_set_in_socket_mode",
                detail=(
                    "SLACK_SIGNING_SECRET is not set. Socket Mode does not need it for request authenticity "
                    "(the connection handshake carries that), but it must be configured before switching to "
                    "HTTP Events mode (SLACK_SOCKET_MODE=false), which fails boot without it."
                ),
            )
        return self


@lru_cache(maxsize=1)
def get_slack_settings() -> SlackSettings:
    """Return the process-wide `SlackSettings` singleton."""
    return SlackSettings()
