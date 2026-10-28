"""Security settings slice: the [security] table of the configuration files.

Exposes ``SecuritySettings``, its ``IssuerEntry`` and the cached
``get_security_settings()`` provider. Values come from the configuration files;
each field may be overridden by ``SECURITY__<FIELD>``, and the dev bypass token,
the slice's only secret, is read only that way. The configuration phase builds
the slice, so an invalid value fails boot naming the file, table and key.
"""

from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only

ASYMMETRIC_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"})

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class IssuerEntry(BaseModel):
    """One trusted JWT issuer: where its keys are, which algorithms it signs with, and the audience it must name."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issuer: str = Field(min_length=1)
    jwks_uri: str
    algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    audience: str | list[str]

    @model_validator(mode="after")
    def validate_entry(self) -> IssuerEntry:
        """Reject an entry that would leave the issuer unusable or unsafe (decisions/security.md)."""
        uri = urlsplit(self.jwks_uri)
        if uri.scheme != "https" and not (uri.scheme == "http" and uri.hostname in _LOOPBACK_HOSTS):
            raise ValueError(f"issuer {self.issuer!r}: jwks_uri must use https (http only on a loopback host)")
        if not self.algorithms:
            raise ValueError(f"issuer {self.issuer!r}: algorithms must not be empty")
        rejected = sorted(set(self.algorithms) - ASYMMETRIC_ALGORITHMS)
        if rejected:
            raise ValueError(f"issuer {self.issuer!r}: algorithms {rejected} are not asymmetric; allowed: RS*, ES*, PS*")
        if not self.audience:
            raise ValueError(f"issuer {self.issuer!r}: audience is required")
        return self


class SecuritySettings(ConfigurationSlice):
    """API authentication and browser access configuration.

    Keys of [security]:
        issuers: trusted JWT issuers, one [[security.issuers]] entry each
            (issuer, jwks_uri, algorithms, audience). Default: none.
        cors_allowed_origins: browser origins allowed to call the API (default: none).
        cors_allowed_methods: methods allowed cross-origin (default: GET and POST,
            the methods the API serves).
        cors_allowed_headers: request headers allowed cross-origin.
        dev_bypass_enabled: allow the static bypass token outside production.

    Environment only:
        SECURITY__DEV_BYPASS_TOKEN: static bearer token accepted when the bypass is
            enabled outside production. Local development only; never set in production.
    """

    model_config = SettingsConfigDict(toml_table_header=("security",), env_prefix="SECURITY__")

    issuers: list[IssuerEntry] = Field(default_factory=list)
    cors_allowed_origins: list[str] = Field(default_factory=list)
    cors_allowed_methods: list[str] = Field(default_factory=lambda: ["GET", "POST"])
    cors_allowed_headers: list[str] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "X-Request-ID", "traceparent"]
    )
    dev_bypass_enabled: bool = False
    dev_bypass_token: SecretStr | None = env_only(
        "Static bearer token the dev bypass accepts; set only with dev_bypass_enabled, never in production.",
        "local",
        default=None,
    )

    @field_validator("issuers")
    @classmethod
    def validate_issuers_are_unique(cls, entries: list[IssuerEntry]) -> list[IssuerEntry]:
        """Reject two entries for one issuer: which keys and audience apply would be ambiguous."""
        seen: set[str] = set()
        for entry in entries:
            if entry.issuer in seen:
                raise ValueError(f"issuer {entry.issuer!r} appears more than once")
            seen.add(entry.issuer)
        return entries

    @field_validator("cors_allowed_origins", "cors_allowed_methods", "cors_allowed_headers")
    @classmethod
    def validate_cors_list_has_no_wildcard(cls, values: list[str]) -> list[str]:
        """Reject a wildcard in any CORS list (decisions/security.md)."""
        if "*" in values:
            raise ValueError("cannot include '*' (see decisions/security.md)")
        return values

    @property
    def issuer_config(self) -> dict[str, dict[str, Any]]:
        """The issuers keyed by issuer, in the shape the JWKS and JWT readers take."""
        return {entry.issuer: entry.model_dump(exclude={"issuer"}) for entry in self.issuers}


@lru_cache(maxsize=1)
def get_security_settings() -> SecuritySettings:
    """Singleton provider for the security settings slice."""
    return SecuritySettings()
