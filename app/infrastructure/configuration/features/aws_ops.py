"""AWS operations feature settings."""

from pydantic import Field

from infrastructure.configuration.base import FeatureSettings


class AWSFeatureSettings(FeatureSettings):
    """AWS operations feature configuration.

    Environment Variables:
        AWS_ADMIN_GROUPS: List of admin group emails for AWS operations
        AWS_OPS_GROUP_NAME: Operations group name

    Example:
        ```python
        from infrastructure.configuration import settings

        admin_groups = settings.aws_feature.AWS_ADMIN_GROUPS
        ops_group = settings.aws_feature.AWS_OPS_GROUP_NAME
        ```
    """

    AWS_ADMIN_GROUPS: list[str] = Field(
        default=["sre-ifs@cds-snc.ca"], alias="AWS_ADMIN_GROUPS"
    )
    AWS_OPS_GROUP_NAME: str = Field(default="", alias="AWS_OPS_GROUP_NAME")
