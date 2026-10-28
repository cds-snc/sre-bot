"""Azure Sentinel vendor settings slice: the [sentinel] table of the configuration files.

Exposes ``SentinelSettings`` and the cached ``get_sentinel_settings()`` provider, read at send
time by ``integrations.sentinel.client``.

The client sends through the Azure Monitor HTTP Data Collector API: the workspace id (customer
id, a non-public value) and its shared key (a secret) come from the environment only. Their
slice-level shape, instead of a [sentinel.tenant] entry, is tolerated until TASK-171 rebuilds the
integration on the Logs Ingestion API (decisions/configuration.md).
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only


class SentinelSettings(ConfigurationSlice):
    """Log Analytics workspace settings for the Sentinel client.

    Keys of [sentinel]:
        log_type: the custom log table events are written to.

    Environment only:
        SENTINEL__CUSTOMER_ID (non-public), SENTINEL__SHARED_KEY (secret). An empty value counts
        as unset; with either unset the client logs an error and sends nothing.
    """

    model_config = SettingsConfigDict(toml_table_header=("sentinel",), env_prefix="SENTINEL__")

    log_type: str = Field(default="DevSREBot", min_length=1, description="Custom log table the events are written to.")
    customer_id: str = env_only("Log Analytics workspace id the events are sent to.", "codespaces", default="")
    shared_key: SecretStr = env_only(
        "Log Analytics workspace shared key that signs each send.", "codespaces", default=SecretStr("")
    )


@lru_cache(maxsize=1)
def get_sentinel_settings() -> SentinelSettings:
    """Return the process-wide ``SentinelSettings`` singleton."""
    return SentinelSettings()
