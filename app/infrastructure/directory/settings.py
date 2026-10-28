"""Directory service settings: the [directory] table of the configuration files."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class DirectorySettings(ConfigurationSlice):
    """Startup behaviour of the directory service.

    Which directory answers a lookup is data (the IdP in a group reference, available when its
    tenant entry is configured), never a setting; Google is the only adapter today.

    Keys of [directory]:
        require_startup_warmup: fail startup when the remote directory warmup fails. Default: false.

    Example:
        ```python
        settings = get_directory_settings()
        if settings.require_startup_warmup:
            # Opt in to fail-fast remote validation before accepting traffic
            ...
        ```
    """

    model_config = SettingsConfigDict(toml_table_header=("directory",), env_prefix="DIRECTORY__")

    require_startup_warmup: bool = Field(
        default=False,
        description="Opt in to fail-fast startup validation against the remote directory",
    )


@lru_cache(maxsize=1)
def get_directory_settings() -> DirectorySettings:
    """Singleton provider for directory infrastructure settings."""
    return DirectorySettings()
