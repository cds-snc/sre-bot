"""Application-level settings and singleton provider."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """App-level settings including CORS policy while SecuritySettings migration is pending."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["local", "ci", "dev", "staging", "production"] = "local"
    DEV_BYPASS_ENABLED: bool = False
    LOG_LEVEL: str = "INFO"
    GIT_SHA: str = "Unknown"
    CORS_ALLOWED_ORIGINS: list[str] = Field(default_factory=list, alias="CORS_ALLOWED_ORIGINS")
    CORS_ALLOWED_METHODS: list[str] = Field(
        default=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        alias="CORS_ALLOWED_METHODS",
    )
    CORS_ALLOWED_HEADERS: list[str] = Field(
        default=["Authorization", "Content-Type", "X-Request-ID", "traceparent"],
        alias="CORS_ALLOWED_HEADERS",
    )

    @model_validator(mode="after")
    def validate_cors_wildcards_with_credentials(self) -> AppSettings:
        """Reject wildcard CORS values because server credentials mode is enabled."""
        wildcard = "*"
        if wildcard in self.CORS_ALLOWED_ORIGINS:
            raise ValueError(
                "CORS_ALLOWED_ORIGINS cannot include '*' when credentials are enabled (see decisions/security.md SEC-1)."
            )
        if wildcard in self.CORS_ALLOWED_METHODS:
            raise ValueError(
                "CORS_ALLOWED_METHODS cannot include '*' when credentials are enabled (see decisions/security.md SEC-1)."
            )
        if wildcard in self.CORS_ALLOWED_HEADERS:
            raise ValueError(
                "CORS_ALLOWED_HEADERS cannot include '*' when credentials are enabled (see decisions/security.md SEC-1)."
            )
        return self


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """Singleton provider for app-level settings."""
    return AppSettings()
