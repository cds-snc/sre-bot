"""Settings for the ATIP commands: the [atip] table."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class AtipSettings(ConfigurationSlice):
    """Where a new ATIP request is announced; the environment file chooses.

    The slice moves with the module to features/atip (TASK-39), which also brings the
    Trello board id into this table.

    Keys of [atip]:
        announce_channel_id: Slack channel id the kickoff and the request text are posted in;
            empty for none (the request still reaches its own channel).
    """

    model_config = SettingsConfigDict(toml_table_header=("atip",), env_prefix="ATIP__")

    announce_channel_id: str = Field(default="", description="Slack channel id ATIP requests are announced in")


@lru_cache(maxsize=1)
def get_atip_settings() -> AtipSettings:
    """Return the process-wide [atip] slice."""
    return AtipSettings()
