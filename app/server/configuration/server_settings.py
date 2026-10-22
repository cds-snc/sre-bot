"""The host's own settings slice: the [server] table."""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class ServerSettings(ConfigurationSlice):
    """Public address, startup-message channel and webhook body cap of the host."""

    model_config = SettingsConfigDict(toml_table_header=("server",), env_prefix="SERVER__")

    public_base_url: str = "http://127.0.0.1:8000"
    sre_test_channel_id: str = ""
    webhook_max_body_bytes: int = 262_144


@lru_cache(maxsize=1)
def get_server_settings() -> ServerSettings:
    """Return the process-wide [server] slice."""
    return ServerSettings()
