"""MaxMind vendor settings slice: the [maxmind] table of the configuration files.

Exposes ``MaxMindSettings``, its tenant entry ``MaxMindTenant``, and the cached
``get_maxmind_settings()`` provider, read at use by ``integrations.maxmind.client``.

MaxMind is read from a local GeoIP2 database, with no credential and no tenant id, so the
entry is the database file the deployment chooses. Boot checks its shape only; whether the
file is present is the healthcheck's (decisions/lifecycle.md). Whether a consumer requires
MaxMind is the consumer's, not this slice's.
"""

from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class MaxMindTenant(BaseModel):
    """The GeoIP2 database this instance reads."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    database_path: str = Field(min_length=1, description="Path to the GeoIP2 City database file.")


class MaxMindSettings(ConfigurationSlice):
    """Vendor settings for the MaxMind GeoIP2 database.

    Keys of [maxmind]:
        [maxmind.tenant] database_path: the database file. Default: none (MaxMind not configured).
    """

    model_config = SettingsConfigDict(toml_table_header=("maxmind",), env_prefix="MAXMIND__")

    tenant: MaxMindTenant | None = Field(default=None, description="The GeoIP2 database this instance reads.")


@lru_cache(maxsize=1)
def get_maxmind_settings() -> MaxMindSettings:
    """Return the process-wide ``MaxMindSettings`` singleton."""
    return MaxMindSettings()
