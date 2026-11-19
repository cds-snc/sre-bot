"""AI writing settings: the [ai_writing] table of the configuration files."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class AIWritingSettings(ConfigurationSlice):
    """Keys of [ai_writing]: model.

    The model is the deploying organisation's value (decisions/configuration.md), so base.toml
    leaves it empty and the environment file sets it. Unset, the capability reports unavailable.
    The output budget and temperature are each caller's, per call.
    """

    model_config = SettingsConfigDict(toml_table_header=("ai_writing",), env_prefix="AI_WRITING__")

    model: str = Field(default="", description="Model the endpoint writes with; empty means unset.")


@lru_cache(maxsize=1)
def get_ai_writing_settings() -> AIWritingSettings:
    """Return the process-wide [ai_writing] slice."""
    return AIWritingSettings()
