"""Slack transport settings slice.

Owns transport-level Slack presentation settings that are independent from
vendor credentials and feature-domain configuration. Read from the
[slack_transport] table.
"""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class SlackTransportSettings(ConfigurationSlice):
    """Transport-level settings for Slack command composition."""

    model_config = SettingsConfigDict(toml_table_header=("slack_transport",), env_prefix="SLACK_TRANSPORT__")

    command_prefix: str = ""


@lru_cache(maxsize=1)
def get_slack_transport_settings() -> SlackTransportSettings:
    """Return the process-wide `SlackTransportSettings` singleton."""

    return SlackTransportSettings()
