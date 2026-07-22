"""Application-level settings and singleton provider."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Minimal app-level settings: prefix, log level, git SHA."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PREFIX: str = Field(
        default="",
        description=(
            "Legacy Slack command-namespace prefix ONLY. No environment meaning. "
            "Being retired per-module via SLACK__COMMAND_PREFIX (TASK-45) and "
            "deleted when the last module cuts over. See decisions/configuration.md "
            "and decisions/transport-slack.md for context."
        ),
    )
    ENVIRONMENT: Literal["local", "ci", "dev", "staging", "production"] = "local"
    DEV_BYPASS_ENABLED: bool = False
    LOG_LEVEL: str = "INFO"
    GIT_SHA: str = "Unknown"


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """Singleton provider for app-level settings."""
    return AppSettings()
