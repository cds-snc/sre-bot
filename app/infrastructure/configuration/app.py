"""Application-level settings and singleton provider."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """App-level settings: deployment identity and the webhook body cap."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    environment: Literal["local", "ci", "production"]
    git_sha: str = "Unknown"
    webhook_max_body_bytes: int = 262_144


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """Singleton provider for app-level settings."""
    return AppSettings()
