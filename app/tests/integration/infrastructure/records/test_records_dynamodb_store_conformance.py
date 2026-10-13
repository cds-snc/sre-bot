"""Moto-backed conformance suite for DynamoDBRecordStore.

Covers DynamoDB-specific serialization only; behaviour shared with the
in-memory fake lives in test_records_store_query_conformance.py.
"""

from decimal import Decimal

import pytest

from infrastructure.records.service import DynamoDBRecordStore

from .conftest import RECORDS_TEST_TABLE as TABLE

pytestmark = pytest.mark.integration


class TestPutAndGet:
    """DynamoDB type round-trip: numbers come back as Decimal, booleans as bool."""

    def test_put_get_roundtrip(self, record_store: DynamoDBRecordStore) -> None:
        item = {"pk": "test-pk-1", "sk": "2026-01-01", "count": 42, "active": True}
        put_result = record_store.put(TABLE, item)
        assert put_result.is_success

        get_result = record_store.get(TABLE, {"pk": "test-pk-1", "sk": "2026-01-01"})
        assert get_result.is_success
        data = get_result.data
        assert data is not None
        assert data["pk"] == "test-pk-1"
        assert data["sk"] == "2026-01-01"
        assert data["count"] == Decimal("42")
        assert data["active"] is True
