"""Spreadsheet service settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class SpreadsheetSettings(InfrastructureSettings):
    """Configuration for the shared spreadsheet provider."""

    provider: Literal["google"] = Field(
        default="google",
        alias="SPREADSHEET_PROVIDER",
        description="Spreadsheet provider implementation to use",
    )


@lru_cache(maxsize=1)
def get_spreadsheet_settings() -> SpreadsheetSettings:
    """Return the singleton spreadsheet settings instance."""
    return SpreadsheetSettings()
