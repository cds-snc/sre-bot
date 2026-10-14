"""Conditional-write store settings owned by the coordination package."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class ConditionalWriteSettings(InfrastructureSettings):
    """Configuration for conditional-write record lifecycle.

    The environment variable names keep the IDEMPOTENCY_ prefix: they are a
    deploy interface.

    Environment Variables:
        IDEMPOTENCY_TTL_SECONDS: TTL for completed records (default: 3600)
        IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS: TTL for in-progress claims (default: 300)
    """

    IDEMPOTENCY_TTL_SECONDS: int = Field(default=3600, alias="IDEMPOTENCY_TTL_SECONDS")
    IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS: int = Field(
        default=300,
        alias="IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS",
    )


@lru_cache(maxsize=1)
def get_conditional_write_settings() -> ConditionalWriteSettings:
    """Singleton provider for conditional-write settings."""
    return ConditionalWriteSettings()
