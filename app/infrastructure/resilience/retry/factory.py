"""Factory for creating retry stores based on configuration."""

from typing import TYPE_CHECKING

import structlog

from infrastructure.resilience.retry.config import RetryConfig
from infrastructure.resilience.retry.dynamodb_store import DynamoDBRetryStore
from infrastructure.resilience.retry.store import InMemoryRetryStore, RetryStore

if TYPE_CHECKING:
    from infrastructure.configuration.infrastructure.retry import RetrySettings

logger = structlog.get_logger()


def create_retry_store(
    config: RetryConfig,
    retry_settings: RetrySettings | None = None,
    backend: str | None = None,
) -> RetryStore:
    """Factory to create appropriate retry store based on configuration.

    Args:
        config: Retry configuration (backoff, max attempts, etc.)
        retry_settings: Narrow retry settings slice.
        backend: Optional backend override (memory, dynamodb).
                If None, uses retry_settings.backend

    Returns:
        Appropriate RetryStore implementation

    Raises:
        ValueError: If unknown backend specified
    """
    resolved_backend = backend or (retry_settings.backend if retry_settings else "memory")

    if resolved_backend == "memory":
        logger.info("creating_in_memory_retry_store")
        return InMemoryRetryStore(config)

    elif resolved_backend == "dynamodb":
        if retry_settings is None:
            raise ValueError("retry_settings is required for DynamoDB backend")
        logger.info(
            "creating_dynamodb_retry_store",
            table_name=retry_settings.dynamodb_table_name,
        )

        return DynamoDBRetryStore(
            config=config,
            table_name=retry_settings.dynamodb_table_name,
            ttl_days=retry_settings.dynamodb_ttl_days,
        )

    else:
        raise ValueError(f"Unknown retry backend: {resolved_backend}. Supported: memory, dynamodb")
