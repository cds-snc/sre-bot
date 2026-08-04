"""AWS operations feature settings."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import FeatureSettings


class AWSFeatureSettings(FeatureSettings):
    """AWS operations feature configuration.

    Environment Variables:
        AWS_ADMIN_GROUPS: List of admin group emails for AWS operations
        AWS_OPS_GROUP_NAME: Operations group name

    Example:
        ```python
        from infrastructure.configuration.features.aws_ops import get_aws_feature_settings

        settings = get_aws_feature_settings()

        admin_groups = settings.AWS_ADMIN_GROUPS
        ops_group = settings.AWS_OPS_GROUP_NAME
        ```
    """

    AWS_ADMIN_GROUPS: list[str] = Field(default=["sre-ifs@cds-snc.ca"], alias="AWS_ADMIN_GROUPS")
    AWS_OPS_GROUP_NAME: str = Field(default="", alias="AWS_OPS_GROUP_NAME")


@lru_cache(maxsize=1)
def get_aws_feature_settings() -> AWSFeatureSettings:
    """Singleton provider for AWS operations feature settings."""
    return AWSFeatureSettings()
