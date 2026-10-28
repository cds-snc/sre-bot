"""Audit trail settings: the [audit] table of the configuration files."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class AuditSettings(ConfigurationSlice):
    """The audit trail's record table.

    Keys of [audit]:
        table_name: the record table holding audit events. Default: sre_bot_audit_trail.
    """

    model_config = SettingsConfigDict(toml_table_header=("audit",), env_prefix="AUDIT__")

    table_name: str = Field(default="sre_bot_audit_trail", description="Record table holding audit events")


@lru_cache(maxsize=1)
def get_audit_settings() -> AuditSettings:
    """Singleton provider for audit settings."""
    return AuditSettings()
