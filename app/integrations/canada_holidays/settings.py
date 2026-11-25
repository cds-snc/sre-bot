"""Canada Holidays vendor settings slice: the [canada_holidays] table of the configuration files.

Exposes ``CanadaHolidaysSettings``, its tenant entry ``CanadaHolidaysTenant``, and the cached
``get_canada_holidays_settings()`` provider, read at use by ``build_canada_holidays_client``.

The Canada Holidays API (canada-holidays.ca) is open source and self-hostable, so its host is
the deployment's choice and lives in the tenant entry, as a regional host does for other
vendors (decisions/configuration.md). It takes no credential. The slice is validated at boot;
whether a consumer requires the API is the consumer's, not this slice's.
"""

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class CanadaHolidaysTenant(BaseModel):
    """The Canada Holidays API this instance reads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str = Field(description="Base URL of the Canada Holidays API, its version path included: https.")

    @field_validator("base_url")
    @classmethod
    def _https(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme == "https" and parts.hostname:
            return value
        raise ValueError("base_url must be an https URL")


class CanadaHolidaysSettings(ConfigurationSlice):
    """Endpoint and transport settings for the Canada Holidays API.

    Keys of [canada_holidays]:
        timeout_seconds: the per-attempt timeout.
        connect_retries: retries of a connection that never opened, set once on the transport.
        [canada_holidays.tenant] base_url: the API host. Default: none (the API is not configured).
    """

    model_config = SettingsConfigDict(toml_table_header=("canada_holidays",), env_prefix="CANADA_HOLIDAYS__")

    tenant: CanadaHolidaysTenant | None = Field(default=None, description="The Canada Holidays API this instance reads.")
    timeout_seconds: float = Field(default=10.0, gt=0, description="Per-attempt HTTP timeout in seconds.")
    connect_retries: int = Field(
        default=2,
        ge=0,
        description="Retries of a connection that never opened (connect error or timeout); a sent request is never repeated.",
    )


@lru_cache(maxsize=1)
def get_canada_holidays_settings() -> CanadaHolidaysSettings:
    """Return the process-wide ``CanadaHolidaysSettings`` singleton."""
    return CanadaHolidaysSettings()
