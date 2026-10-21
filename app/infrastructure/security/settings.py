"""Security settings slice: JWT issuers, the CORS policy and the local dev bypass.

Exposes ``SecuritySettings`` and the cached ``get_security_settings()`` provider. Each
field reads the environment variable of the same name, matched case-insensitively.
Lifespan's configuration phase builds the slice, so an invalid value fails boot
naming the key.
"""

from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecuritySettings(BaseSettings):
    """API authentication and browser access configuration.

    Environment Variables:
        issuer_config: JSON map of JWT issuer to its jwks_uri, algorithms and
            required audience. A value that is not a JSON object means no issuers.
        cors_allowed_origins: JSON list of browser origins allowed to call the API
            (default: none).
        cors_allowed_methods: JSON list of methods allowed cross-origin
            (default: GET and POST, the methods the API serves).
        cors_allowed_headers: JSON list of request headers allowed cross-origin.
        dev_bypass_enabled: Allow the static bypass token outside production.
        dev_bypass_token: Static bearer token accepted when the bypass is enabled
            outside production. Local development only; never set in production.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    issuer_config: dict[str, dict[str, Any]] | None = None
    cors_allowed_origins: list[str] = Field(default_factory=list)
    cors_allowed_methods: list[str] = Field(default_factory=lambda: ["GET", "POST"])
    cors_allowed_headers: list[str] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "X-Request-ID", "traceparent"]
    )
    dev_bypass_enabled: bool = False
    dev_bypass_token: SecretStr | None = None

    @field_validator("issuer_config", mode="before")
    @classmethod
    def validate_issuer_config(cls, v: object) -> Any:
        """Treat a missing or non-object ISSUER_CONFIG as no issuers."""
        if not isinstance(v, dict):
            return {}
        return v

    @model_validator(mode="after")
    def validate_issuer_config_requires_audience(self) -> SecuritySettings:
        """Reject issuer entries that do not define an audience."""
        for issuer, cfg in (self.issuer_config or {}).items():
            if not isinstance(cfg, dict) or not cfg.get("audience"):
                raise ValueError(f"ISSUER_CONFIG entry for issuer '{issuer}' is missing required 'audience'")
        return self

    @model_validator(mode="after")
    def validate_cors_lists_have_no_wildcard(self) -> SecuritySettings:
        """Reject a wildcard in any CORS list (decisions/security.md)."""
        for key, values in (
            ("CORS_ALLOWED_ORIGINS", self.cors_allowed_origins),
            ("CORS_ALLOWED_METHODS", self.cors_allowed_methods),
            ("CORS_ALLOWED_HEADERS", self.cors_allowed_headers),
        ):
            if "*" in values:
                raise ValueError(f"{key} cannot include '*' (see decisions/security.md).")
        return self


@lru_cache(maxsize=1)
def get_security_settings() -> SecuritySettings:
    """Singleton provider for the security settings slice."""
    return SecuritySettings()
