"""Settings for the Notify API-key-leak handler: the [notify_api_key_leak] table."""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class NotifyApiKeyLeakSettings(ConfigurationSlice):
    """Where the API-key-leak response posts and whom it mentions; the environment file chooses."""

    model_config = SettingsConfigDict(toml_table_header=("notify_api_key_leak",), env_prefix="NOTIFY_API_KEY_LEAK__")

    channel_id: str = ""
    oncall_group_id: str = ""


@lru_cache(maxsize=1)
def get_notify_api_key_leak_settings() -> NotifyApiKeyLeakSettings:
    """Return the process-wide [notify_api_key_leak] slice."""
    return NotifyApiKeyLeakSettings()
