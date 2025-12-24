"""Retry system infrastructure settings."""

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class RetrySettings(InfrastructureSettings):
    """Retry system configuration for failed operations.

    Provides centralized configuration for the infrastructure retry system used
    by modules to handle failed async operations with exponential backoff.

    Environment Variables:
        RETRY_ENABLED: Enable retry system (default: True)
        RETRY_BACKEND: Backend type - 'memory', 'dynamodb', or 'sqs'
        RETRY_DYNAMODB_TABLE_NAME: DynamoDB table name (if using DynamoDB backend)
        RETRY_DYNAMODB_TTL_DAYS: TTL for DynamoDB retry records (default: 7 days)
        RETRY_MAX_ATTEMPTS: Maximum retry attempts before DLQ (default: 5)
        RETRY_BASE_DELAY_SECONDS: Base exponential backoff delay (default: 60s)
        RETRY_MAX_DELAY_SECONDS: Maximum backoff delay (default: 3600s = 1h)
        RETRY_BATCH_SIZE: Records to process per batch (default: 10)
        RETRY_CLAIM_LEASE_SECONDS: Claim duration (default: 300s = 5min)

    Retry Backends:
        - memory: In-memory queue (development, testing)
        - dynamodb: DynamoDB-backed persistent queue (production)
        - sqs: AWS SQS-backed queue (production, high-throughput)

    Exponential Backoff:
        Delay calculation: min(base_delay * (2 ^ attempt), max_delay)

        Example with defaults (base=60s, max=3600s):
            Attempt 1: 60s
            Attempt 2: 120s
            Attempt 3: 240s
            Attempt 4: 480s
            Attempt 5: 960s (capped at 3600s for higher attempts)

    Example:
        ```python
        from infrastructure.services import get_settings

        settings = get_settings()

        if settings.retry.enabled:
            backend = settings.retry.backend
            max_attempts = settings.retry.max_attempts
            # Configure retry system...
        ```
    """

    enabled: bool = Field(
        default=True,
        alias="RETRY_ENABLED",
        description="Enable retry system for failed operations",
    )
    backend: str = Field(
        default="memory",
        alias="RETRY_BACKEND",
        description="Retry backend: 'memory', 'dynamodb', or 'sqs'",
    )
    dynamodb_table_name: str = Field(
        default="srebot-retry-records",
        alias="RETRY_DYNAMODB_TABLE_NAME",
        description="DynamoDB table name for retry records (if using DynamoDB backend)",
    )
    dynamodb_ttl_days: int = Field(
        default=7,
        alias="RETRY_DYNAMODB_TTL_DAYS",
        description="Time-to-live for retry records in DynamoDB (days)",
    )
    max_attempts: int = Field(
        default=5,
        alias="RETRY_MAX_ATTEMPTS",
        description="Maximum retry attempts before moving to DLQ",
    )
    base_delay_seconds: int = Field(
        default=60,
        alias="RETRY_BASE_DELAY_SECONDS",
        description="Base delay for exponential backoff (seconds)",
    )
    max_delay_seconds: int = Field(
        default=3600,
        alias="RETRY_MAX_DELAY_SECONDS",
        description="Maximum delay for exponential backoff (seconds, 1 hour)",
    )
    batch_size: int = Field(
        default=10,
        alias="RETRY_BATCH_SIZE",
        description="Number of records to process per batch",
    )
    claim_lease_seconds: int = Field(
        default=300,
        alias="RETRY_CLAIM_LEASE_SECONDS",
        description="Duration to hold claim on retry record (seconds, 5 minutes)",
    )
