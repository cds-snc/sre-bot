"""Fixtures for idempotency cache tests."""

import pytest
from infrastructure.idempotency.dynamodb import DynamoDBCache
from infrastructure.idempotency.factory import reset_cache
from infrastructure.operations.result import OperationResult, OperationStatus


@pytest.fixture
def sample_response():
    """Sample response data for caching."""
    return {
        "success": True,
        "status_code": 200,
        "data": {"id": "123", "status": "active"},
    }


@pytest.fixture
def operation_result_success():
    """Create a successful OperationResult."""
    return OperationResult(
        status=OperationStatus.SUCCESS,
        message="Operation successful",
        data={"Item": {"response_json": {"S": '{"success": true}'}}},
    )


@pytest.fixture
def operation_result_failure():
    """Create a failed OperationResult."""
    return OperationResult(
        status=OperationStatus.FAILURE,
        message="Operation failed",
        error_code="DynamoDBError",
    )


@pytest.fixture
def mock_dynamodb_cache():
    """Create a DynamoDB cache for testing with mocked AWS calls."""
    cache = DynamoDBCache(table_name="test_idempotency")
    return cache


@pytest.fixture(autouse=True)
def reset_cache_singleton():
    """Reset the cache singleton before each test."""
    reset_cache()
    yield
    reset_cache()
