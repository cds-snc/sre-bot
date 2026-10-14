"""Protocol contract tests for RecordStore."""

from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from contracts.records import KeySchema, RecordStore, RecordTable
from infrastructure.records import get_record_store
from infrastructure.records.in_memory import InMemoryRecordStore
from infrastructure.records.service import DynamoDBRecordStore

TABLE = RecordTable(name="test_table", key=KeySchema(partition="PK", sort="SK"))


@pytest.mark.unit
def test_dynamodb_record_store_satisfies_protocol() -> None:
    mock_dynamo = MagicMock()
    store = DynamoDBRecordStore(dynamodb=mock_dynamo)

    assert isinstance(store, RecordStore)


@pytest.mark.unit
def test_in_memory_record_store_satisfies_protocol() -> None:
    store = InMemoryRecordStore()

    assert isinstance(store, RecordStore)


@pytest.mark.unit
def test_protocol_is_runtime_checkable() -> None:
    assert getattr(RecordStore, "_is_runtime_protocol", False)


@pytest.mark.unit
def test_record_store_dep_override_with_fake() -> None:
    app = FastAPI()
    fake = InMemoryRecordStore()

    @app.get("/probe")
    def probe(
        store: RecordStore = Depends(get_record_store),
    ) -> dict[str, bool]:
        result = store.put(TABLE, {"PK": "A", "SK": "1"})
        return {"ok": result.is_success}

    app.dependency_overrides[get_record_store] = lambda: fake
    try:
        client = TestClient(app)
        response = client.get("/probe")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

        stored = fake.get(TABLE, {"PK": "A", "SK": "1"})
        assert stored.is_success
    finally:
        app.dependency_overrides.clear()
