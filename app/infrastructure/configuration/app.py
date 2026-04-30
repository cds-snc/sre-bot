"""Application-level settings and singleton provider."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Minimal app-level settings: prefix, log level, git SHA."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PREFIX: str = ""
    LOG_LEVEL: str = "INFO"
    GIT_SHA: str = "Unknown"

    @property
    def is_production(self) -> bool:
        """True when PREFIX is empty (production deployment)."""
        return not bool(self.PREFIX)


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """Singleton provider for app-level settings."""
    return AppSettings()
