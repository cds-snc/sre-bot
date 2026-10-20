"""Security settings slice: JWT issuers, the CORS policy and the local dev bypass.

Exposes ``SecuritySettings`` and the cached ``get_security_settings()`` provider. Each
field reads the environment variable of the same name. Lifespan's configuration
phase builds the slice, so an invalid value fails boot naming the key.
"""

from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    """API authentication and browser access configuration.

    Environment Variables:
        ISSUER_CONFIG: JSON map of JWT issuer to its jwks_uri, algorithms and
            required audience. A value that is not a JSON object means no issuers.
        CORS_ALLOWED_ORIGINS: JSON list of browser origins allowed to call the API
            (default: none).
        CORS_ALLOWED_METHODS: JSON list of methods allowed cross-origin
            (default: GET and POST, the methods the API serves).
        CORS_ALLOWED_HEADERS: JSON list of request headers allowed cross-origin.
        DEV_BYPASS_ENABLED: Allow the static bypass token outside production.
        DEV_BYPASS_TOKEN: Static bearer token accepted when the bypass is enabled
            outside production. Local development only; never set in production.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    ISSUER_CONFIG: dict[str, dict[str, Any]] | None = None
    CORS_ALLOWED_ORIGINS: list[str] = Field(default_factory=list)
    CORS_ALLOWED_METHODS: list[str] = Field(default_factory=lambda: ["GET", "POST"])
    CORS_ALLOWED_HEADERS: list[str] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "X-Request-ID", "traceparent"]
    )
    DEV_BYPASS_ENABLED: bool = False
    DEV_BYPASS_TOKEN: SecretStr | None = None

    @field_validator("ISSUER_CONFIG", mode="before")
    @classmethod
    def validate_issuer_config(cls, v: object) -> Any:
        """Treat a missing or non-object ISSUER_CONFIG as no issuers."""
        if not isinstance(v, dict):
            return {}
        return v

    @model_validator(mode="after")
    def validate_issuer_config_requires_audience(self) -> SecuritySettings:
        """Reject issuer entries that do not define an audience."""
        for issuer, cfg in (self.ISSUER_CONFIG or {}).items():
            if not isinstance(cfg, dict) or not cfg.get("audience"):
                raise ValueError(f"ISSUER_CONFIG entry for issuer '{issuer}' is missing required 'audience'")
        return self

    @model_validator(mode="after")
    def validate_cors_lists_have_no_wildcard(self) -> SecuritySettings:
        """Reject a wildcard in any CORS list (decisions/security.md)."""
        for key, values in (
            ("CORS_ALLOWED_ORIGINS", self.CORS_ALLOWED_ORIGINS),
            ("CORS_ALLOWED_METHODS", self.CORS_ALLOWED_METHODS),
            ("CORS_ALLOWED_HEADERS", self.CORS_ALLOWED_HEADERS),
        ):
            if "*" in values:
                raise ValueError(f"{key} cannot include '*' (see decisions/security.md).")
        return self


@lru_cache(maxsize=1)
def get_security_settings() -> SecuritySettings:
    """Singleton provider for the security settings slice."""
    return SecuritySettings()
