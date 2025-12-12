"""Retry system configuration.

This module defines configuration for the retry system behavior.
"""

from dataclasses import dataclass


@dataclass
class RetryConfig:
    """Configuration for retry system behavior.

    This dataclass controls retry behavior such as backoff timing,
    max attempts, batch processing, and claim leases.

    Attributes:
        max_attempts: Maximum number of retry attempts before moving to DLQ
        base_delay_seconds: Base delay for exponential backoff (first retry)
        max_delay_seconds: Maximum delay between retries (cap for exponential backoff)
        batch_size: Number of records to process in a single batch
        claim_lease_seconds: How long a worker can hold a claim on a record

    Example:
        # Default configuration
        config = RetryConfig()

        # Custom configuration
        config = RetryConfig(
            max_attempts=3,
            base_delay_seconds=30,
            batch_size=50
        )
    """

    max_attempts: int = 5
    base_delay_seconds: int = 60  # 1 minute
    max_delay_seconds: int = 3600  # 1 hour
    batch_size: int = 10
    claim_lease_seconds: int = 300  # 5 minutes

    def __post_init__(self) -> None:
        """Validate configuration values."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay_seconds < 1:
            raise ValueError("base_delay_seconds must be at least 1")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.claim_lease_seconds < 1:
            raise ValueError("claim_lease_seconds must be at least 1")
