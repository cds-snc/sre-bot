"""AWS operations feature settings: the [cloud_operations] table of the configuration files."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class AWSFeatureSettings(ConfigurationSlice):
    """Who may run the legacy /aws admin commands.

    A group's address is an identifier, not a secret: membership is the control. TASK-88
    deletes the setting when the rebuilt AWS surfaces declare their permissions.

    Keys of [cloud_operations]:
        aws_admin_groups: Google group addresses whose members may run /aws admin commands;
            empty denies every caller.
    """

    model_config = SettingsConfigDict(toml_table_header=("cloud_operations",), env_prefix="CLOUD_OPERATIONS__")

    AWS_ADMIN_GROUPS: list[str] = Field(
        default_factory=list, description="Google group addresses whose members may run /aws admin commands"
    )


@lru_cache(maxsize=1)
def get_aws_feature_settings() -> AWSFeatureSettings:
    """Singleton provider for AWS operations feature settings."""
    return AWSFeatureSettings()
