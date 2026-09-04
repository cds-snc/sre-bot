"""Directory service settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class DirectorySettings(InfrastructureSettings):
    """Directory core service configuration.

    Controls which IDP provider backs the directory service and governs
    startup behaviour for ECS task readiness.

    Environment Variables:
        DIRECTORY_PROVIDER: IDP backend to activate (default: google)
        DIRECTORY_REQUIRE_STARTUP_WARMUP: Fail startup if warmup fails (default: False)
        DIRECTORY_CACHE_TTL_SECONDS: In-process membership cache TTL (default: 60)
        DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS: Startup warmup timeout in seconds

    Example:
        ```python
        from infrastructure.directory.settings import get_directory_settings

        settings = get_directory_settings()

        provider = settings.provider
        if settings.require_startup_warmup:
            # Opt in to fail-fast remote validation before accepting traffic
            ...
        ```
    """

    provider: Literal["google", "entra_id"] = Field(
        default="google",
        alias="DIRECTORY_PROVIDER",
        description="IDP backend - 'google' or 'entra_id'",
    )
    require_startup_warmup: bool = Field(
        default=False,
        alias="DIRECTORY_REQUIRE_STARTUP_WARMUP",
        description="Opt in to fail-fast startup validation against the remote directory",
    )
    startup_preload_groups: list[str] = Field(
        default_factory=list,
        description="Group keys to pre-load into cache at startup",
    )
    cache_ttl_seconds: int = Field(
        default=60,
        alias="DIRECTORY_CACHE_TTL_SECONDS",
        description="In-process membership cache TTL in seconds",
    )
    startup_warmup_timeout_seconds: int = Field(
        default=2,
        alias="DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS",
        description="Timeout for the lightweight startup warmup probe",
    )


@lru_cache(maxsize=1)
def get_directory_settings() -> DirectorySettings:
    """Singleton provider for directory infrastructure settings."""
    return DirectorySettings()
