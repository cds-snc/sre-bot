"""OpenAI vendor settings slice: the [openai] table of the configuration files.

Exposes ``OpenAISettings``, its tenant entry ``OpenAITenant``, and the cached
``get_openai_settings()`` provider.

Only the connection belongs here (API key, endpoint, timeout and connection retries).
The model is the AI writing capability's [ai_writing] model, and the output budget and
temperature are each caller's (decisions/configuration.md). OpenAI has no tenant id, so the tenant entry is the
model endpoint it reaches (decisions/configuration.md). The slice is validated at boot;
whether a consumer requires OpenAI is the consumer's, not this slice's.
"""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only

_LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


class OpenAITenant(BaseModel):
    """The OpenAI-compatible endpoint this instance works with."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = Field(description="Base URL of the OpenAI-compatible API: https, or http on a loopback host.")

    @field_validator("base_url")
    @classmethod
    def _https_or_loopback(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme == "https" and parts.hostname:
            return value
        if parts.scheme == "http" and parts.hostname in _LOOPBACK_HOSTS:
            return value
        raise ValueError("base_url must be an https URL, or http on a loopback host")


class OpenAISettings(ConfigurationSlice):
    """Vendor credential, endpoint and connection settings for the OpenAI API.

    Keys of [openai]:
        connect_retries, timeout_seconds.
        [openai.tenant] base_url: the endpoint. Default: none (OpenAI not configured).

    Environment only:
        OPENAI__API_KEY. An empty value counts as unset. A tenant entry needs the key and the
        key needs a tenant entry, so OpenAI is never half configured.
    """

    model_config = SettingsConfigDict(toml_table_header=("openai",), env_prefix="OPENAI__")

    tenant: OpenAITenant | None = Field(default=None, description="The model endpoint this instance works with.")
    api_key: SecretStr = env_only("API key for the tenant's endpoint.", "codespaces", default=SecretStr(""))
    # Must outlast generating the largest output budget a caller passes: at 60-100 tokens/sec a large
    # completion takes well over a minute, so a 60s timeout aborted requests
    # the model was still legitimately writing.
    timeout_seconds: float = 180.0
    # Retries cover a connection that never opened (httpcore retries only ConnectError and
    # ConnectTimeout), so a completion request that reached the endpoint is never re-sent:
    # it is not idempotent and every attempt is billed (decisions/outbound-clients.md).
    connect_retries: int = Field(default=2, ge=0)

    @model_validator(mode="after")
    def _tenant_and_key_go_together(self) -> OpenAISettings:
        has_key = bool(self.api_key.get_secret_value())
        if self.tenant is not None and not has_key:
            raise ValueError("OPENAI__API_KEY is required when [openai.tenant] is set")
        if self.tenant is None and has_key:
            raise ValueError("OPENAI__API_KEY is set but [openai.tenant] is not")
        return self

    @property
    def base_url(self) -> str:
        """The tenant's base URL, or empty when OpenAI is not configured."""
        return self.tenant.base_url if self.tenant else ""


@lru_cache(maxsize=1)
def get_openai_settings() -> OpenAISettings:
    """Return the process-wide ``OpenAISettings`` singleton."""
    return OpenAISettings()
