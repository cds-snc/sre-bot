"""Application-level settings and singleton provider."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """App-level settings: deployment identity and the webhook body cap."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["local", "ci", "production"]
    GIT_SHA: str = "Unknown"
    WEBHOOK_MAX_BODY_BYTES: int = Field(default=262_144, alias="WEBHOOK_MAX_BODY_BYTES")


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """Singleton provider for app-level settings."""
    return AppSettings()
