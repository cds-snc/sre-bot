"""ATIP feature settings."""

from pydantic import Field

from infrastructure.configuration.base import FeatureSettings


class AtipSettings(FeatureSettings):
    """ATIP (Access to Information and Privacy) feature configuration.

    Environment Variables:
        ATIP_ANNOUNCE_CHANNEL: Slack channel ID for ATIP announcements

    Example:
        ```python
        from infrastructure.configuration import settings

        announce_channel = settings.atip.ATIP_ANNOUNCE_CHANNEL
        ```
    """

    ATIP_ANNOUNCE_CHANNEL: str | None = Field(
        default=None, alias="ATIP_ANNOUNCE_CHANNEL"
    )
