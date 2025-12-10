"""SRE operations feature settings."""

from pydantic import Field

from infrastructure.configuration.base import FeatureSettings


class SreOpsSettings(FeatureSettings):
    """SRE operations feature configuration.

    Environment Variables:
        SRE_OPS_CHANNEL_ID: Slack channel ID for SRE operations notifications

    Example:
        ```python
        from infrastructure.configuration import settings

        ops_channel = settings.sre_ops.SRE_OPS_CHANNEL_ID
        ```
    """

    SRE_OPS_CHANNEL_ID: str = Field(default="", alias="SRE_OPS_CHANNEL_ID")
