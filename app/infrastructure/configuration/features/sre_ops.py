"""SRE operations feature settings: the [sre_ops] table of the configuration files."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class SreOpsSettings(ConfigurationSlice):
    """The channel the startup message and ops notifications go to.

    The field name stays until the slice moves with its surface (TASK-40), which also
    standardises the key.

    Keys of [sre_ops]:
        sre_ops_channel_id: Slack channel id for SRE operations notifications; empty for none.
    """

    model_config = SettingsConfigDict(toml_table_header=("sre_ops",), env_prefix="SRE_OPS__")

    SRE_OPS_CHANNEL_ID: str = Field(default="", description="Slack channel id for SRE operations notifications")


@lru_cache(maxsize=1)
def get_sre_ops_settings() -> SreOpsSettings:
    """Singleton provider for SRE operations feature settings."""
    return SreOpsSettings()
