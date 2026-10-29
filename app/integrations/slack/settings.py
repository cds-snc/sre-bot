"""Slack vendor settings slice: the [slack] table of the configuration files.

Exposes `SlackSettings`, its tenant entry `SlackTenant`, and the cached `get_slack_settings()` provider.

Non-secret values (per-call timeout, retry budget, error-code catalogues) come from
[slack]; the workspace this instance works with from [slack.tenant] (production.toml
and local.toml each name theirs; ci.toml none). The tokens and the signing secret are
read only from the environment as SLACK__<FIELD>, as a single-workspace Bolt app is
configured (decisions/configuration.md). A present tenant entry needs the bot token,
and any secret set without a tenant entry fails, so Slack is never half configured.
The tenant entry is the expected tenant; checking each request against it, and the
optional enterprise id, are TASK-157's.

Whether and how the transport runs is the [slack_transport] slice
(server/slack/settings.py). The rules that join the two (the transport switched on
needs the tenant entry, the bot token and its delivery mode's credential) run in the
configuration phase (server/configuration/host_configuration.py), not here.

Feature-domain configuration (channel IDs, user-group IDs) lives with the consuming feature.
"""

from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only

_SECRETS = ("bot_token", "user_token", "app_token", "signing_secret")


class SlackTenant(BaseModel):
    """The Slack tenant this instance works with: the expected tenant, in Slack's terms."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    team_id: str = Field(description="Slack workspace (team) id, as auth.test returns it.")

    @field_validator("team_id")
    @classmethod
    def _strip_and_reject_blank(cls, value: str) -> str:
        # The id is opaque (Slack documents no format), so only blankness is checked.
        value = value.strip()
        if not value:
            raise ValueError("team_id must not be blank")
        return value

    @property
    def tenant_id(self) -> str:
        """Return Slack's tenant id for this entry: the workspace (team) id."""
        return self.team_id


class SlackSettings(ConfigurationSlice):
    """Vendor credential, tenant and classification settings for Slack.

    Keys of [slack]:
        request_timeout_seconds, retry_max_attempts, transient_retry_after_seconds,
        unauthorized_errors, not_found_errors, transient_errors.
        [slack.tenant] team_id: the workspace this instance works with. Default: none.

    Environment only:
        SLACK__BOT_TOKEN, SLACK__USER_TOKEN, SLACK__APP_TOKEN, SLACK__SIGNING_SECRET.
        An empty value counts as unset.
    """

    model_config = SettingsConfigDict(toml_table_header=("slack",), env_prefix="SLACK__")

    tenant: SlackTenant | None = Field(default=None, description="The Slack workspace this instance works with.")

    bot_token: SecretStr = env_only("Bot token (xoxb-) the app acts with.", "codespaces", default=SecretStr(""))
    user_token: SecretStr = env_only("User token (xoxp-) for the calls a bot token cannot make.", "codespaces", default=SecretStr(""))
    app_token: SecretStr | None = env_only("App-level token (xapp-) Socket Mode connects with.", "codespaces", default=None)
    signing_secret: SecretStr | None = env_only("Signing secret HTTP Events mode verifies requests with.", "local", default=None)

    request_timeout_seconds: int = 10
    retry_max_attempts: int = 2
    transient_retry_after_seconds: int = Field(
        default=30,
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
        description="Slack Web API error codes classified as UNAUTHORIZED.",
    )
    not_found_errors: list[str] = Field(
        default=["channel_not_found", "user_not_found", "users_not_found", "message_not_found", "no_such_subteam"],
        description="Slack Web API error codes classified as NOT_FOUND.",
    )
    transient_errors: list[str] = Field(
        default=["ratelimited", "internal_error", "fatal_error", "service_unavailable", "request_timeout"],
        description="Slack Web API error codes classified as TRANSIENT_ERROR.",
    )

    @field_validator("app_token", "signing_secret", mode="before")
    @classmethod
    def _empty_secret_is_absent(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _tenant_and_secrets_go_together(self) -> SlackSettings:
        if self.tenant is not None and not self.bot_token:
            raise ValueError("SLACK__BOT_TOKEN is required when [slack.tenant] is set")
        if self.tenant is None:
            for field in _SECRETS:
                if getattr(self, field):
                    raise ValueError(f"SLACK__{field.upper()} is set but [slack.tenant] team_id is not")
        return self


@lru_cache(maxsize=1)
def get_slack_settings() -> SlackSettings:
    """Return the process-wide `SlackSettings` singleton."""
    return SlackSettings()
