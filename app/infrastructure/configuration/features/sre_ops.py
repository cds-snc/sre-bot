"""SRE operations feature settings."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import FeatureSettings


class SreOpsSettings(FeatureSettings):
    """SRE operations feature configuration.

    Environment Variables:
        SRE_OPS_CHANNEL_ID: Slack channel ID for SRE operations notifications

    Example:
        ```python
        from infrastructure.configuration.features.sre_ops import get_sre_ops_settings

        settings = get_sre_ops_settings()

        ops_channel = settings.SRE_OPS_CHANNEL_ID
        ```
    """

    SRE_OPS_CHANNEL_ID: str = Field(default="", alias="SRE_OPS_CHANNEL_ID")


@lru_cache(maxsize=1)
def get_sre_ops_settings() -> SreOpsSettings:
    """Singleton provider for SRE operations feature settings."""
    return SreOpsSettings()
