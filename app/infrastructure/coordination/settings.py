"""Coordination settings: the [coordination] table of the configuration files."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class ConditionalWriteSettings(ConfigurationSlice):
    """The conditional-write store's table and record lifetimes.

    Keys of [coordination]:
        table_name: the DynamoDB table holding the records. Default: sre_bot_idempotency.
        record_ttl_seconds: lifetime of a completed record. Default: 3600.
        in_progress_ttl_seconds: lifetime of an in-progress claim before another worker may take it. Default: 300.
    """

    model_config = SettingsConfigDict(toml_table_header=("coordination",), env_prefix="COORDINATION__")

    table_name: str = Field(default="sre_bot_idempotency", description="Table holding the conditional-write records")
    record_ttl_seconds: int = Field(default=3600, description="Lifetime of a completed record")
    in_progress_ttl_seconds: int = Field(default=300, description="Lifetime of an in-progress claim")


@lru_cache(maxsize=1)
def get_conditional_write_settings() -> ConditionalWriteSettings:
    """Singleton provider for conditional-write settings."""
    return ConditionalWriteSettings()
