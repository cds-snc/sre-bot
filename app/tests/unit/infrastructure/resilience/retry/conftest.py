"""Shared fixtures for retry system tests."""

import pytest
from typing import Dict, Any

from infrastructure.resilience.retry import (
    RetryConfig,
    RetryRecord,
    RetryResult,
    InMemoryRetryStore,
)


@pytest.fixture
def retry_config_factory():
    """Factory for creating RetryConfig instances."""

    def _factory(
        max_attempts: int = 5,
        base_delay_seconds: int = 60,
        max_delay_seconds: int = 3600,
        batch_size: int = 10,
        claim_lease_seconds: int = 300,
    ) -> RetryConfig:
        return RetryConfig(
            max_attempts=max_attempts,
            base_delay_seconds=base_delay_seconds,
            max_delay_seconds=max_delay_seconds,
            batch_size=batch_size,
            claim_lease_seconds=claim_lease_seconds,
        )

    return _factory


@pytest.fixture
def retry_record_factory():
    """Factory for creating RetryRecord instances."""

    def _factory(
        operation_type: str = "test.operation",
        payload: Dict[str, Any] | None = None,
        id: str | None = None,
        attempts: int = 0,
        last_error: str | None = None,
    ) -> RetryRecord:
        if payload is None:
            payload = {"task_id": "test-task", "data": "test data"}

        return RetryRecord(
            operation_type=operation_type,
            payload=payload,
            id=id,
            attempts=attempts,
            last_error=last_error,
        )

    return _factory


@pytest.fixture
def retry_store(retry_config_factory):
    """Create a fresh InMemoryRetryStore for testing."""
    config = retry_config_factory()
    return InMemoryRetryStore(config)


@pytest.fixture
def mock_processor():
    """Mock processor that returns configurable results."""

    class MockProcessor:
        def __init__(self):
            self.processed_records = []
            self.result = RetryResult.SUCCESS

        def process_record(self, record: RetryRecord) -> RetryResult:
            self.processed_records.append(record)
            return self.result

        def set_result(self, result: RetryResult):
            self.result = result

        def reset(self):
            self.processed_records = []
            self.result = RetryResult.SUCCESS

    return MockProcessor()
