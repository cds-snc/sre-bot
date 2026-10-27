"""OpenAI vendor settings slice: the [openai] table of the configuration files.

Exposes ``OpenAISettings``, its tenant entry ``OpenAITenant``, and the cached
``get_openai_settings()`` provider.

Only OpenAI-transport concerns belong here (API key, model endpoint, token/timeout
limits). Feature-domain configuration (what gets summarized, how history is bounded)
lives with the consuming feature. OpenAI has no tenant id, so the tenant entry is the
model endpoint it reaches (decisions/configuration.md). The slice is validated at boot;
whether a consumer requires OpenAI is the consumer's, not this slice's.
"""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice

_LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


class OpenAITenant(BaseModel):
    """The OpenAI-compatible model endpoint this instance works with."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = Field(description="Base URL of the OpenAI-compatible API: https, or http on a loopback host.")
    model: str = Field(min_length=1, description="Model the endpoint serves for chat completions.")

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
    """Vendor credential, endpoint and tuning settings for the OpenAI API.

    Keys of [openai]:
        max_output_tokens, temperature, timeout_seconds.
        [openai.tenant] base_url, model: the model endpoint. Default: none (OpenAI not configured).

    Environment only:
        OPENAI__API_KEY. An empty value counts as unset. A tenant entry needs the key and the
        key needs a tenant entry, so OpenAI is never half configured.
    """

    model_config = SettingsConfigDict(toml_table_header=("openai",), env_prefix="OPENAI__")

    tenant: OpenAITenant | None = Field(default=None, description="The model endpoint this instance works with.")
    api_key: SecretStr = Field(default=SecretStr(""), repr=False, description="API key for the tenant's endpoint.")
    max_output_tokens: int = 3000
    # Summarising wants reproducibility, not creativity, so a temperature of 0
    # is worth having where the model supports it. It is omitted by default
    # because reasoning-style models -- including the gateway's current default
    # -- reject the parameter outright with a 400, which fails the whole
    # request. Set 0.0 to opt in; any negative value omits it.
    temperature: float = -1.0
    # Must outlast generating max_output_tokens: at 60-100 tokens/sec a large
    # completion takes well over a minute, so a 60s timeout aborted requests
    # the model was still legitimately writing.
    timeout_seconds: float = 180.0

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

    @property
    def model(self) -> str:
        """The tenant's model, or empty when OpenAI is not configured."""
        return self.tenant.model if self.tenant else ""


@lru_cache(maxsize=1)
def get_openai_settings() -> OpenAISettings:
    """Return the process-wide ``OpenAISettings`` singleton."""
    return OpenAISettings()
