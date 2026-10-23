"""Vendor settings for Slack credentials and the Slack tenant entry.

Exposes `SlackSettings`, its tenant entry `SlackTenant`, and the cached `get_slack_settings()` provider.

`SLACK_TEAM_ID` is the source of the interim Slack tenant entry (`SlackTenant`,
read through `SlackSettings.tenant`), until TASK-111.9 moves the entry into the
[slack] table (decisions/configuration.md). Readers use the entry, never the flat
field. The entry is the expected tenant; checking each request against it is TASK-157's.
The id is optional here; an empty value counts as absent and a present one must be
non-blank. The id is opaque (Slack documents no format), so no pattern is checked
and no network call is made.

Whether and how the transport runs is the [slack_transport] slice
(server/slack/settings.py). The rules that join the two (the transport switched on
needs the tenant entry, the bot token and its delivery mode's credential) run in the
configuration phase (server/configuration/host_configuration.py), not here.

Vendor credentials only (tokens, secrets, per-call timeout, retry budget,
error-code catalogues). Feature-domain configuration (channel IDs, user-group IDs)
lives with the consuming feature.
"""

from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SlackTenant(BaseModel):
    """The Slack tenant this instance works with: the expected tenant, in Slack's terms."""

    model_config = ConfigDict(frozen=True)

    team_id: str = Field(description="Slack workspace (team) id, as auth.test returns it.")

    @property
    def tenant_id(self) -> str:
        """Return Slack's tenant id for this entry: the workspace (team) id."""
        return self.team_id


class SlackSettings(BaseSettings):
    """Vendor credential, transport, and classification settings for Slack."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    team_id: str | None = Field(
        default=None,
        alias="SLACK_TEAM_ID",
        description="Slack workspace (team) id this instance works with, as auth.test returns it; required when [slack_transport] enabled is true.",
    )

    bot_token: str = Field(default="", alias="SLACK_BOT_TOKEN")
    user_token: str = Field(default="", alias="SLACK_USER_TOKEN", repr=False)
    app_token: str | None = Field(default=None, alias="SLACK_APP_TOKEN")
    signing_secret: str | None = Field(default=None, alias="SLACK_SIGNING_SECRET")

    request_timeout_seconds: int = Field(default=10, alias="SLACK_REQUEST_TIMEOUT_SECONDS")
    retry_max_attempts: int = Field(default=2, alias="SLACK_RETRY_MAX_ATTEMPTS")
    transient_retry_after_seconds: int = Field(
        default=30,
        alias="SLACK_TRANSIENT_RETRY_AFTER_SECONDS",
        description="Retry hint attached to transient classifications when Slack sends no Retry-After header, in seconds.",
    )

    unauthorized_errors: list[str] = Field(
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
    not_found_errors: list[str] = Field(
        default=["channel_not_found", "user_not_found", "users_not_found", "message_not_found", "no_such_subteam"],
        alias="SLACK_NOT_FOUND_ERRORS",
        description="Slack Web API error codes classified as NOT_FOUND.",
    )
    transient_errors: list[str] = Field(
        default=["ratelimited", "internal_error", "fatal_error", "service_unavailable", "request_timeout"],
        alias="SLACK_TRANSIENT_ERRORS",
        description="Slack Web API error codes classified as TRANSIENT_ERROR.",
    )

    @property
    def tenant(self) -> SlackTenant | None:
        """Return the Slack tenant entry, or None when Slack is not configured."""
        if self.team_id is None:
            return None
        return SlackTenant(team_id=self.team_id.strip())

    @field_validator("team_id", mode="before")
    @classmethod
    def _empty_team_id_is_absent(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _reject_blank_team_id(self) -> SlackSettings:
        if self.team_id is not None and not self.team_id.strip():
            raise ValueError("SLACK_TEAM_ID must not be blank when set")
        return self


@lru_cache(maxsize=1)
def get_slack_settings() -> SlackSettings:
    """Return the process-wide `SlackSettings` singleton."""
    return SlackSettings()
