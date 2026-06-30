"""ATIP feature settings."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import FeatureSettings


class AtipSettings(FeatureSettings):
    """ATIP (Access to Information and Privacy) feature configuration.

    Environment Variables:
        ATIP_ANNOUNCE_CHANNEL: Slack channel ID for ATIP announcements

    Example:
        ```python
        from infrastructure.configuration.features.atip import get_atip_settings

        settings = get_atip_settings()

        announce_channel = settings.ATIP_ANNOUNCE_CHANNEL
        ```
    """

    ATIP_ANNOUNCE_CHANNEL: str | None = Field(
        default=None, alias="ATIP_ANNOUNCE_CHANNEL"
    )


@lru_cache(maxsize=1)
def get_atip_settings() -> AtipSettings:
    """Singleton provider for ATIP feature settings."""
    return AtipSettings()
