"""Cloud spending settings: the [cloud_operations_spending] table of the configuration files.

The sheet id is a non-public value (decisions/configuration.md): declared empty in
base.toml, set only from the environment as CLOUD_OPERATIONS_SPENDING__SHEET_ID.
"""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only


class CloudOperationsSpendingSettings(ConfigurationSlice):
    """Where the spending report is written.

    Environment only (non-public values):
        CLOUD_OPERATIONS_SPENDING__SHEET_ID.
    """

    model_config = SettingsConfigDict(toml_table_header=("cloud_operations_spending",), env_prefix="CLOUD_OPERATIONS_SPENDING__")

    sheet_id: str = env_only("Google Sheets spreadsheet the AWS spending report is written to.", "codespaces", default="")


@lru_cache(maxsize=1)
def get_cloud_operations_spending_settings() -> CloudOperationsSpendingSettings:
    """Return the process-wide [cloud_operations_spending] slice."""
    return CloudOperationsSpendingSettings()
