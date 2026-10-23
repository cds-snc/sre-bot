"""Slack transport settings slice.

Owns whether and how the Slack transport runs and how it names its commands,
apart from the Slack client's credentials and tenant entry ([slack],
integrations/slack/settings.py). Read from the [slack_transport] table. The
rules that join the two slices run in the configuration phase
(server/configuration/host_configuration.py), and only host code imports this
slice: the legacy modules read the command prefix from contracts/slack/transport.py.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class SlackTransportSettings(ConfigurationSlice):
    """Transport-level settings for running Slack and composing its commands."""

    model_config = SettingsConfigDict(toml_table_header=("slack_transport",), env_prefix="SLACK_TRANSPORT__")

    enabled: bool = Field(default=False, description="Run the Slack transport on this deployment.")
    socket_mode: bool = Field(
        default=True,
        description="Receive Slack events over Socket Mode; false selects HTTP Events mode, which needs the signing secret.",
    )
    command_prefix: str = Field(
        default="", description="Prefix added to every slash command name, so two bots share a workspace."
    )


@lru_cache(maxsize=1)
def get_slack_transport_settings() -> SlackTransportSettings:
    """Return the process-wide `SlackTransportSettings` singleton."""

    return SlackTransportSettings()
