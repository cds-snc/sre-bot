"""Whole-table read conformance shared by the in-memory fake and the DynamoDB store.

Every case runs against both implementations through the parametrized
``any_record_store`` fixture (moto for DynamoDB). Results are compared as
sets because the read's order is unspecified. The multi-page case seeds five
350 KB items, which moto splits over three 1 MB Scan pages as DynamoDB does,
so paging and the cap are proven against real page boundaries.
"""

from typing import Any

import pytest

from contracts.operations.status import OperationStatus
from contracts.records import READ_LIMIT_EXCEEDED, RecordStore

from .conftest import RECORDS_TEST_TABLE as TABLE

pytestmark = pytest.mark.integration

LARGE_VALUE = "x" * 350_000


def _keys(items: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {(item["pk"], item["sk"]) for item in items}


def test_an_empty_table_reads_as_no_items(any_record_store: RecordStore) -> None:
    result = any_record_store.read_all(TABLE, max_items=5)

    assert result.is_success
    assert result.data == []


def test_every_item_of_every_partition_is_returned(any_record_store: RecordStore) -> None:
    for pk, sk in [("a", "1"), ("a", "2"), ("b", "1"), ("c", "9")]:
        assert any_record_store.put(TABLE, {"pk": pk, "sk": sk, "value": sk}).is_success

    result = any_record_store.read_all(TABLE, max_items=10)

    assert result.is_success
    assert _keys(result.data) == {("a", "1"), ("a", "2"), ("b", "1"), ("c", "9")}


def test_items_come_back_without_store_bookkeeping(any_record_store: RecordStore) -> None:
    assert any_record_store.put_if_not_exists(TABLE, {"pk": "a", "sk": "1", "value": "v"}).data is True

    result = any_record_store.read_all(TABLE, max_items=5)

    assert result.data == [{"pk": "a", "sk": "1", "value": "v"}]


def test_writes_and_deletes_completed_before_the_read_are_reflected(any_record_store: RecordStore) -> None:
    any_record_store.put(TABLE, {"pk": "a", "sk": "1", "value": "old"})
    any_record_store.delete(TABLE, {"pk": "a", "sk": "1"})
    any_record_store.put(TABLE, {"pk": "b", "sk": "1", "value": "new"})

    result = any_record_store.read_all(TABLE, max_items=5)

    assert result.data == [{"pk": "b", "sk": "1", "value": "new"}]


def test_a_table_holding_exactly_the_cap_is_returned_whole(any_record_store: RecordStore) -> None:
    for sk in ["1", "2", "3"]:
        any_record_store.put(TABLE, {"pk": "a", "sk": sk})

    result = any_record_store.read_all(TABLE, max_items=3)

    assert result.is_success
    assert len(result.data) == 3


def test_a_table_holding_more_than_the_cap_is_an_error_not_a_truncated_list(any_record_store: RecordStore) -> None:
    for sk in ["1", "2", "3", "4"]:
        any_record_store.put(TABLE, {"pk": "a", "sk": sk})

    result = any_record_store.read_all(TABLE, max_items=3)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == READ_LIMIT_EXCEEDED
    assert result.data is None


class TestLargerThanOneBackendPage:
    """Five 350 KB items span three 1 MB Scan pages on the DynamoDB store."""

    @pytest.fixture(autouse=True)
    def _seed(self, any_record_store: RecordStore) -> None:
        for index in range(5):
            assert any_record_store.put(TABLE, {"pk": f"p{index}", "sk": "1", "value": LARGE_VALUE}).is_success

    def test_every_page_is_read(self, any_record_store: RecordStore) -> None:
        result = any_record_store.read_all(TABLE, max_items=5)

        assert result.is_success
        assert _keys(result.data) == {(f"p{index}", "1") for index in range(5)}

    def test_the_cap_holds_across_pages(self, any_record_store: RecordStore) -> None:
        result = any_record_store.read_all(TABLE, max_items=4)

        assert result.error_code == READ_LIMIT_EXCEEDED


@pytest.mark.parametrize("max_items", [0, -3])
def test_a_cap_below_one_raises(any_record_store: RecordStore, max_items: int) -> None:
    with pytest.raises(ValueError, match="max_items must be at least 1"):
        any_record_store.read_all(TABLE, max_items=max_items)
