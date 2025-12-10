"""MaxMind integration settings."""

from pydantic import Field

from infrastructure.configuration.base import IntegrationSettings


class MaxMindSettings(IntegrationSettings):
    """MaxMind GeoIP database configuration.

    Environment Variables:
        MAXMIND_DB_PATH: Path to MaxMind GeoLite2-City database file

    Example:
        ```python
        from infrastructure.configuration import settings

        db_path = settings.maxmind.MAXMIND_DB_PATH
        ```
    """

    MAXMIND_DB_PATH: str = Field(
        default="./geodb/GeoLite2-City.mmdb", alias="MAXMIND_DB_PATH"
    )
