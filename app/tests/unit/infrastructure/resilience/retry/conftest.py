"""Shared fixtures for retry system tests."""

import pytest
from typing import Dict, Any
from unittest.mock import MagicMock

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


@pytest.fixture
def mock_dynamodb_next():
    """Mock dynamodb_next module for testing."""
    from unittest.mock import MagicMock
    from infrastructure.operations import OperationResult

    mock = MagicMock()

    # Default successful responses
    mock.put_item.return_value = OperationResult.success(data={})
    mock.get_item.return_value = OperationResult.success(data={"Item": {}})
    mock.query.return_value = OperationResult.success(data={"Items": [], "Count": 0})
    mock.update_item.return_value = OperationResult.success(data={})
    mock.delete_item.return_value = OperationResult.success(data={})

    return mock


@pytest.fixture
def dynamodb_retry_store(retry_config_factory, mock_dynamodb_next, monkeypatch):
    """Create DynamoDB retry store with mocked dynamodb_next."""
    monkeypatch.setattr(
        "infrastructure.resilience.retry.dynamodb_store.dynamodb_next",
        mock_dynamodb_next,
    )

    from infrastructure.resilience.retry.dynamodb_store import DynamoDBRetryStore

    config = retry_config_factory()
    store = DynamoDBRetryStore(
        config=config,
        table_name="test-retry-table",
        ttl_days=30,
    )
    store._mock_dynamodb_next = mock_dynamodb_next  # Attach for test access
    return store


@pytest.fixture
def mock_settings():
    """Create mock settings object for retry tests with memory backend."""
    settings = MagicMock()
    settings.retry.backend = "memory"
    settings.retry.max_attempts = 5
    settings.retry.base_delay_seconds = 60
    settings.retry.max_delay_seconds = 3600
    settings.retry.batch_size = 10
    settings.retry.claim_lease_seconds = 300
    settings.retry.dynamodb_table_name = "retry-records"
    settings.retry.dynamodb_region = "ca-central-1"
    settings.retry.dynamodb_ttl_days = 30
    return settings


@pytest.fixture
def mock_settings_with_dynamodb():
    """Create mock settings object for retry tests with DynamoDB backend."""
    settings = MagicMock()
    settings.retry.backend = "dynamodb"
    settings.retry.max_attempts = 5
    settings.retry.base_delay_seconds = 60
    settings.retry.max_delay_seconds = 3600
    settings.retry.batch_size = 10
    settings.retry.claim_lease_seconds = 300
    settings.retry.dynamodb_table_name = "test-retry-records"
    settings.retry.dynamodb_region = "ca-central-1"
    settings.retry.dynamodb_ttl_days = 30
    return settings
