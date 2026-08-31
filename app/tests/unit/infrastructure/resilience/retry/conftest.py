"""Shared fixtures for retry system tests."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from infrastructure.configuration.infrastructure.retry import RetrySettings
from infrastructure.resilience.retry import (
    InMemoryRetryStore,
    RetryConfig,
    RetryRecord,
    RetryResult,
)
from infrastructure.resilience.retry.dynamodb_store import DynamoDBRetryStore


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
        payload: dict[str, Any] | None = None,
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
def mock_dynamodb_client():
    """Provide a DynamoDB client double with boto3 response-shaped defaults."""
    mock = MagicMock(spec=["put_item", "get_item", "delete_item", "update_item", "query", "get_paginator"])

    # Default successful responses
    mock.put_item.return_value = {}
    mock.get_item.return_value = {"Item": {}}
    mock.query.return_value = {"Items": [], "Count": 0}
    mock.update_item.return_value = {}
    mock.delete_item.return_value = {}
    mock.get_paginator.return_value.paginate.return_value = [{"Count": 0}]

    return mock


@pytest.fixture
def dynamodb_retry_store(retry_config_factory, mock_dynamodb_client):
    """Create a DynamoDB retry store with an injected client double."""
    config = retry_config_factory()
    store = DynamoDBRetryStore(
        mock_dynamodb_client,
        config=config,
        table_name="test-retry-table",
        ttl_days=30,
    )
    store._mock_dynamodb = mock_dynamodb_client  # Attach for test access
    return store


@pytest.fixture
def mock_settings():
    """Create mock RetrySettings for retry tests with memory backend."""
    settings = MagicMock(spec=RetrySettings)
    settings.backend = "memory"
    settings.max_attempts = 5
    settings.base_delay_seconds = 60
    settings.max_delay_seconds = 3600
    settings.batch_size = 10
    settings.claim_lease_seconds = 300
    settings.dynamodb_table_name = "retry-records"
    settings.dynamodb_region = "ca-central-1"
    settings.dynamodb_ttl_days = 30
    return settings


@pytest.fixture
def mock_settings_with_dynamodb():
    """Create mock RetrySettings for retry tests with DynamoDB backend."""
    settings = MagicMock(spec=RetrySettings)
    settings.backend = "dynamodb"
    settings.max_attempts = 5
    settings.base_delay_seconds = 60
    settings.max_delay_seconds = 3600
    settings.batch_size = 10
    settings.claim_lease_seconds = 300
    settings.dynamodb_table_name = "test-retry-records"
    settings.dynamodb_region = "ca-central-1"
    settings.dynamodb_ttl_days = 30
    return settings
