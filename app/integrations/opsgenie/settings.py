"""Opsgenie vendor settings slice: the [opsgenie] table of the configuration files.

Exposes ``OpsGenieSettings``, its tenant entry ``OpsGenieTenant``, and the cached
``get_opsgenie_settings()`` provider, read at use by ``integrations.opsgenie.client``.

Opsgenie serves each account from one region (api.opsgenie.com or api.eu.opsgenie.com), so the
tenant entry is the regional API host. The integration key is a secret read from the
environment. The slice is validated at boot; whether a consumer requires Opsgenie is the
consumer's, not this slice's.
"""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only


class OpsGenieTenant(BaseModel):
    """The Opsgenie API region this instance works with."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    api_url: str = Field(description="Base URL of the account's regional Opsgenie API: https.")

    @field_validator("api_url")
    @classmethod
    def _https(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme == "https" and parts.hostname:
            return value
        raise ValueError("api_url must be an https URL")


class OpsGenieSettings(ConfigurationSlice):
    """Vendor credential, endpoint and timeout settings for the Opsgenie API.

    Keys of [opsgenie]:
        timeout_seconds.
        [opsgenie.tenant] api_url: the regional API host. Default: none (Opsgenie not configured).

    Environment only:
        OPSGENIE__INTEGRATIONS_KEY. An empty value counts as unset. A tenant entry needs the key
        and the key needs a tenant entry, so Opsgenie is never half configured.
    """

    model_config = SettingsConfigDict(toml_table_header=("opsgenie",), env_prefix="OPSGENIE__")

    tenant: OpsGenieTenant | None = Field(default=None, description="The Opsgenie API region this instance works with.")
    integrations_key: SecretStr = env_only("API key sent as the GenieKey authorization.", "codespaces", default=SecretStr(""))
    timeout_seconds: float = Field(default=30.0, gt=0, description="Per-request HTTP timeout in seconds.")

    @model_validator(mode="after")
    def _tenant_and_key_go_together(self) -> OpsGenieSettings:
        has_key = bool(self.integrations_key.get_secret_value())
        if self.tenant is not None and not has_key:
            raise ValueError("OPSGENIE__INTEGRATIONS_KEY is required when [opsgenie.tenant] is set")
        if self.tenant is None and has_key:
            raise ValueError("OPSGENIE__INTEGRATIONS_KEY is set but [opsgenie.tenant] is not")
        return self


@lru_cache(maxsize=1)
def get_opsgenie_settings() -> OpsGenieSettings:
    """Return the process-wide ``OpsGenieSettings`` singleton."""
    return OpsGenieSettings()
