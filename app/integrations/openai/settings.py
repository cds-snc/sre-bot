"""Vendor settings for the OpenAI API client.

Exposes ``OpenAISettings`` -- the vendor-credential and transport surface
consumed by ``app.integrations.openai.client`` -- and the cached
``get_openai_settings()`` provider.

Only OpenAI-transport concerns belong here (API key, model, token/timeout
limits, base URL). Feature-domain configuration (what gets summarized, how
history is bounded) lives with the consuming feature.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class OpenAISettings(BaseSettings):
    """Vendor-credential and transport settings for the OpenAI API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    API_KEY: SecretStr = Field(alias="OPENAI_API_KEY")
    MODEL: str = Field(default="gpt-5.4-nano", alias="OPENAI_MODEL")
    MAX_OUTPUT_TOKENS: int = Field(default=800, alias="OPENAI_MAX_OUTPUT_TOKENS")
    TIMEOUT_SECONDS: float = Field(default=30.0, alias="OPENAI_TIMEOUT_SECONDS")
    BASE_URL: str = Field(default="https://ai.cdssandbox.xyz", alias="OPENAI_BASE_URL")


@lru_cache(maxsize=1)
def get_openai_settings() -> OpenAISettings:
    """Return the process-wide ``OpenAISettings`` singleton."""
    return OpenAISettings()
