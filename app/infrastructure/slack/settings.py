"""Slack transport settings slice.

Owns transport-level Slack presentation settings that are independent from
vendor credentials and feature-domain configuration.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SlackTransportSettings(BaseSettings):
    """Transport-level settings for Slack command composition."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    COMMAND_PREFIX: str = Field(default="", alias="SLACK__COMMAND_PREFIX")


@lru_cache(maxsize=1)
def get_slack_transport_settings() -> SlackTransportSettings:
    """Return the process-wide `SlackTransportSettings` singleton."""

    return SlackTransportSettings()
