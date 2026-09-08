"""Drive service settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class DriveSettings(InfrastructureSettings):
    """Configuration for the shared Drive provider."""

    provider: Literal["google"] = Field(
        default="google",
        alias="DRIVE_PROVIDER",
        description="Drive provider implementation to use",
    )


@lru_cache(maxsize=1)
def get_drive_settings() -> DriveSettings:
    """Return the singleton Drive settings instance."""
    return DriveSettings()
