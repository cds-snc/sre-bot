"""GC Notify vendor settings slice: the [notify] table of the configuration files.

Exposes ``NotifySettings``, its tenant entry ``NotifyTenant``, and the cached
``get_notify_settings()`` provider, read at use by ``integrations.notify.client``.

The deployment chooses which GC Notify host it reaches, so the tenant entry is that API
host. The credentials are secrets read from the environment. The slice is validated at
boot; whether a consumer requires Notify is the consumer's, not this slice's.
"""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice

_CREDENTIALS = {"sre_user_name": "NOTIFY__SRE_USER_NAME", "sre_client_secret": "NOTIFY__SRE_CLIENT_SECRET"}


class NotifyTenant(BaseModel):
    """The GC Notify API this instance works with."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    api_url: str = Field(description="Base URL of the GC Notify API: https.")

    @field_validator("api_url")
    @classmethod
    def _https(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme == "https" and parts.hostname:
            return value
        raise ValueError("api_url must be an https URL")


class NotifySettings(ConfigurationSlice):
    """Vendor credential, endpoint and timeout settings for the GC Notify API.

    Keys of [notify]:
        timeout_seconds.
        [notify.tenant] api_url: the API host. Default: none (Notify not configured).

    Environment only:
        NOTIFY__SRE_USER_NAME, NOTIFY__SRE_CLIENT_SECRET. An empty value counts as unset. A
        tenant entry needs both and either needs a tenant entry, so Notify is never half configured.
    """

    model_config = SettingsConfigDict(toml_table_header=("notify",), env_prefix="NOTIFY__")

    tenant: NotifyTenant | None = Field(default=None, description="The GC Notify API this instance works with.")
    sre_user_name: SecretStr = Field(default=SecretStr(""), repr=False, description="Client id the JWT is issued for.")
    sre_client_secret: SecretStr = Field(default=SecretStr(""), repr=False, description="Secret the JWT is signed with.")
    timeout_seconds: float = Field(default=60.0, gt=0, description="Per-request HTTP timeout in seconds.")

    @model_validator(mode="after")
    def _tenant_and_credentials_go_together(self) -> NotifySettings:
        present = {name: bool(getattr(self, field).get_secret_value()) for field, name in _CREDENTIALS.items()}
        if self.tenant is not None:
            for name, is_set in present.items():
                if not is_set:
                    raise ValueError(f"{name} is required when [notify.tenant] is set")
        else:
            for name, is_set in present.items():
                if is_set:
                    raise ValueError(f"{name} is set but [notify.tenant] is not")
        return self


@lru_cache(maxsize=1)
def get_notify_settings() -> NotifySettings:
    """Return the process-wide ``NotifySettings`` singleton."""
    return NotifySettings()
