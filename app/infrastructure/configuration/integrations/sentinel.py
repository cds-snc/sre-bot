"""Azure Sentinel integration settings."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import IntegrationSettings


class SentinelSettings(IntegrationSettings):
    """Azure Sentinel configuration.

    Environment Variables:
        SENTINEL_CUSTOMER_ID: Azure Sentinel workspace customer ID
        SENTINEL_LOG_TYPE: Log type identifier (default: DevSREBot)
        SENTINEL_SHARED_KEY: Azure Sentinel shared key for authentication

    Example:
        ```python
        from infrastructure.configuration import get_settings

        settings = get_settings()

        customer_id = settings.sentinel.SENTINEL_CUSTOMER_ID
        log_type = settings.sentinel.SENTINEL_LOG_TYPE
        ```
    """

    SENTINEL_CUSTOMER_ID: str | None = Field(default=None, alias="SENTINEL_CUSTOMER_ID")
    SENTINEL_LOG_TYPE: str = Field(default="DevSREBot", alias="SENTINEL_LOG_TYPE")
    SENTINEL_SHARED_KEY: str | None = Field(default=None, alias="SENTINEL_SHARED_KEY")


@lru_cache(maxsize=1)
def get_sentinel_settings() -> SentinelSettings:
    """Singleton provider for Azure Sentinel integration settings."""
    return SentinelSettings()
