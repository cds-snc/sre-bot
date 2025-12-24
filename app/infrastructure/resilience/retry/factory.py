"""Factory for creating retry stores based on configuration."""

import structlog
from infrastructure.services.providers import get_settings
from infrastructure.resilience.retry.config import RetryConfig
from infrastructure.resilience.retry.store import RetryStore, InMemoryRetryStore
from infrastructure.resilience.retry.dynamodb_store import DynamoDBRetryStore


logger = structlog.get_logger()
settings = get_settings()


def create_retry_store(config: RetryConfig, backend: str | None = None) -> RetryStore:
    """Factory to create appropriate retry store based on configuration.

    Args:
        config: Retry configuration (backoff, max attempts, etc.)
        backend: Optional backend override (memory, dynamodb).
                If None, uses settings.retry.backend

    Returns:
        Appropriate RetryStore implementation

    Raises:
        ValueError: If unknown backend specified

    Examples:
        >>> config = RetryConfig()
        >>> store = create_retry_store(config)  # Uses settings.retry.backend
        >>> store = create_retry_store(config, backend="memory")  # Force memory
        >>> store = create_retry_store(config, backend="dynamodb")  # Force DynamoDB
    """
    backend = backend or settings.retry.backend

    if backend == "memory":
        logger.info("creating_in_memory_retry_store")
        return InMemoryRetryStore(config)

    elif backend == "dynamodb":
        logger.info(
            "creating_dynamodb_retry_store",
            table_name=settings.retry.dynamodb_table_name,
        )

        return DynamoDBRetryStore(
            config=config,
            table_name=settings.retry.dynamodb_table_name,
            ttl_days=settings.retry.dynamodb_ttl_days,
        )

    else:
        raise ValueError(
            f"Unknown retry backend: {backend}. Supported: memory, dynamodb"
        )
