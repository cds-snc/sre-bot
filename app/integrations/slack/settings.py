"""Vendor settings for the Slack shield.

Exposes `SlackSettings` — the vendor-credential, transport, delivery-mode,
and error-classification surface consumed by `SlackShield` — and the
cached `get_slack_settings()` provider.

Vendor credentials and transport settings only (tokens, secrets, per-call
timeout, retry budget, delivery mode, error-code catalogues). Feature-domain
configuration (channel IDs, user-group IDs) lives with the consuming feature.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    APP_TOKEN: Optional[str] = Field(default=None, alias="SLACK_APP_TOKEN")
    SIGNING_SECRET: Optional[str] = Field(default=None, alias="SLACK_SIGNING_SECRET")

    REQUEST_TIMEOUT_SECONDS: int = Field(
        default=10, alias="SLACK_REQUEST_TIMEOUT_SECONDS"
    )
    RETRY_MAX_ATTEMPTS: int = Field(default=2, alias="SLACK_RETRY_MAX_ATTEMPTS")

    NOT_FOUND_CODES: list[str] = Field(
        default=[
            "channel_not_found",
            "user_not_found",
            "message_not_found",
            "view_not_found",
            "file_not_found",
            "subteam_not_found",
        ],
        alias="SLACK_NOT_FOUND_CODES",
    )
    UNAUTHORIZED_CODES: list[str] = Field(
        default=[
            "not_authed",
            "invalid_auth",
            "account_inactive",
            "token_revoked",
            "token_expired",
            "missing_scope",
            "no_permission",
        ],
        alias="SLACK_UNAUTHORIZED_CODES",
    )
    TRANSIENT_CODES: list[str] = Field(
        default=[
            "ratelimited",
            "fatal_error",
            "internal_error",
            "service_unavailable",
        ],
        alias="SLACK_TRANSIENT_CODES",
    )

    @model_validator(mode="after")
    def _validate_transport_credentials(self) -> "SlackSettings":
        if not self.ENABLED:
            return self
        if self.SOCKET_MODE and not self.APP_TOKEN:
            raise ValueError(
                "SLACK_APP_TOKEN is required when SLACK_SOCKET_MODE=true and SLACK_ENABLED=true"
            )
        if not self.SOCKET_MODE and not self.SIGNING_SECRET:
            raise ValueError(
                "SLACK_SIGNING_SECRET is required when SLACK_SOCKET_MODE=false and SLACK_ENABLED=true"
            )
        return self


@lru_cache(maxsize=1)
def get_slack_settings() -> SlackSettings:
    """Return the process-wide `SlackSettings` singleton."""
    return SlackSettings()
