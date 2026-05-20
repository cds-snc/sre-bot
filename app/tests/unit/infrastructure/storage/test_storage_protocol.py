"""Protocol contract tests for StorageService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from infrastructure.storage import get_storage_service
from infrastructure.storage.protocol import StorageService
from infrastructure.storage.service import DynamoDBStorageService
from tests.unit.infrastructure.storage.fake_storage import FakeStorageService


@pytest.mark.unit
def test_dynamodb_storage_satisfies_protocol() -> None:
    mock_dynamo = MagicMock()
    storage = DynamoDBStorageService(dynamodb=mock_dynamo)

    assert isinstance(storage, StorageService)


@pytest.mark.unit
def test_fake_storage_satisfies_protocol() -> None:
    storage = FakeStorageService()

    assert isinstance(storage, StorageService)


@pytest.mark.unit
def test_protocol_is_runtime_checkable() -> None:
    assert getattr(StorageService, "_is_runtime_protocol", False)


@pytest.mark.unit
def test_storage_service_dep_override_with_fake() -> None:
    app = FastAPI()
    fake = FakeStorageService()

    @app.get("/probe")
    def probe(
        storage: StorageService = Depends(get_storage_service),
    ) -> dict[str, bool]:
        result = storage.put("test_table", {"PK": "A", "SK": "1"})
        return {"ok": result.is_success}

    app.dependency_overrides[get_storage_service] = lambda: fake
    try:
        client = TestClient(app)
        response = client.get("/probe")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

        stored = fake.get("test_table", {"PK": "A", "SK": "1"})
        assert stored.is_success
    finally:
        app.dependency_overrides.clear()
