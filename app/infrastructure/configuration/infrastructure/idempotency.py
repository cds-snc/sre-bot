"""Idempotency infrastructure settings."""

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class IdempotencySettings(InfrastructureSettings):
    """Idempotency cache configuration for preventing duplicate operations.

    Environment Variables:
        IDEMPOTENCY_TTL_SECONDS: Time-to-live for idempotency cache entries (default: 3600s = 1h)

    Example:
        ```python
        from infrastructure.configuration import settings

        ttl = settings.idempotency.IDEMPOTENCY_TTL_SECONDS
        # Configure idempotency cache with TTL...
        ```
    """

    IDEMPOTENCY_TTL_SECONDS: int = Field(default=3600, alias="IDEMPOTENCY_TTL_SECONDS")
