"""Directory infrastructure settings."""

from typing import Literal

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class DirectorySettings(InfrastructureSettings):
    """Directory core service configuration.

    Controls which IDP provider backs the directory service and governs
    startup behaviour for ECS task readiness.

    Environment Variables:
        DIRECTORY_PROVIDER: IDP backend to activate (default: google)
        DIRECTORY_REQUIRE_STARTUP_WARMUP: Fail startup if warmup fails (default: True)
        DIRECTORY_CACHE_TTL_SECONDS: In-process membership cache TTL (default: 60)

    Example:
        ```python
        from infrastructure.services import get_settings

        settings = get_settings()

        provider = settings.directory.provider
        if settings.directory.require_startup_warmup:
            # Enforce warmup before accepting traffic
            ...
        ```
    """

    provider: Literal["google", "entra_id"] = Field(
        default="google",
        alias="DIRECTORY_PROVIDER",
        description="IDP backend - 'google' or 'entra_id'",
    )
    require_startup_warmup: bool = Field(
        default=True,
        alias="DIRECTORY_REQUIRE_STARTUP_WARMUP",
        description="Fail startup when provider warmup fails",
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
