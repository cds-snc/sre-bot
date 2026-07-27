"""Unit tests for access sync job status storage wrapper."""

import json
from unittest.mock import MagicMock, patch

import pytest
from packages.access.sync.job_status_store import JobStatusStore

from infrastructure.operations import OperationResult, OperationStatus


@pytest.mark.unit
def test_put_serializes_record_as_json_with_ttl() -> None:
    """Put should write idempotency key, JSON payload, and computed ttl."""
    storage = MagicMock()
    storage.put.return_value = OperationResult.success()
    store = JobStatusStore(storage=storage)

    with patch("packages.access.sync.job_status_store.time.time", return_value=1_000):
        store.put(
            key="job-123",
            record={"job_id": "job-123", "status": "in_progress"},
            ttl_seconds=90,
        )

    storage.put.assert_called_once()
    args, _ = storage.put.call_args
    assert args[0] == "sre_bot_idempotency"
    item = args[1]
    assert item["idempotency_key"] == "job-123"
    assert item["ttl"] == 1_090
    assert json.loads(item["record_json"]) == {"job_id": "job-123", "status": "in_progress"}


@pytest.mark.unit
def test_get_returns_deserialized_record() -> None:
    """Get should deserialize JSON payload when storage hit succeeds."""
    storage = MagicMock()
    storage.get.return_value = OperationResult.success(
        data={
            "idempotency_key": "job-124",
            "record_json": '{"job_id":"job-124","status":"completed"}',
        }
    )
    store = JobStatusStore(storage=storage)

    result = store.get("job-124")

    assert result == {"job_id": "job-124", "status": "completed"}
    storage.get.assert_called_once_with("sre_bot_idempotency", {"idempotency_key": "job-124"})


@pytest.mark.unit
def test_get_returns_none_when_not_found() -> None:
    """Get should return None when the storage service reports a miss."""
    storage = MagicMock()
    storage.get.return_value = OperationResult.error(OperationStatus.NOT_FOUND, message="missing")
    store = JobStatusStore(storage=storage)

    assert store.get("job-missing") is None


@pytest.mark.unit
def test_get_returns_none_when_record_json_missing_or_malformed() -> None:
    """Get should return None for malformed or missing JSON payloads."""
    storage = MagicMock()
    store = JobStatusStore(storage=storage)

    storage.get.return_value = OperationResult.success(data={"idempotency_key": "job-1"})
    assert store.get("job-1") is None

    storage.get.return_value = OperationResult.success(data={"idempotency_key": "job-2", "record_json": "{"})
    assert store.get("job-2") is None
