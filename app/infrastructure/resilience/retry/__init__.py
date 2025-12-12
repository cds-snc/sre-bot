"""Generic retry system for failed operations.

This module provides infrastructure for retrying failed operations across all
feature modules. It replaces module-specific retry implementations with a
centralized, configurable system.

Architecture:
- RetryRecord: Generic data model for retry operations
- RetryStore: Storage interface with in-memory and future persistent implementations
- RetryWorker: Generic batch processor for retry operations
- RetryProcessor: Protocol for module-specific retry logic
- RetryConfig: Configuration for retry behavior

Usage:
    from infrastructure.resilience.retry import (
        RetryRecord,
        RetryStore,
        InMemoryRetryStore,
        RetryWorker,
        RetryProcessor,
        RetryConfig,
        RetryResult,
    )

    # Create store
    store = InMemoryRetryStore()

    # Implement processor for your module
    class MyProcessor(RetryProcessor):
        def process_record(self, record: RetryRecord) -> RetryResult:
            # Module-specific logic
            ...

    # Create worker
    config = RetryConfig(max_attempts=5, base_delay_seconds=60)
    worker = RetryWorker(store, MyProcessor(), config)

    # Process batch
    worker.process_batch()
"""

from infrastructure.resilience.retry.config import RetryConfig
from infrastructure.resilience.retry.models import RetryRecord, RetryResult
from infrastructure.resilience.retry.store import InMemoryRetryStore, RetryStore
from infrastructure.resilience.retry.worker import RetryProcessor, RetryWorker
from infrastructure.resilience.retry.factory import create_retry_store

__all__ = [
    # Models
    "RetryRecord",
    "RetryResult",
    # Configuration
    "RetryConfig",
    # Store
    "RetryStore",
    "InMemoryRetryStore",
    # Worker
    "RetryWorker",
    "RetryProcessor",
    # Factory
    "create_retry_store",
]
