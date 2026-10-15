"""Conformance suite shared by the in-memory fake and the DynamoDB store.

Every case runs against both implementations through the parametrized
``any_record_store`` fixture, so the fake cannot drift from the real store:
full-key writes and reads, conditional create, key-condition queries, sort
order, total-cap limits and logical index queries.
"""

import pytest

from contracts.operations.status import OperationStatus
from contracts.records import RecordQuery, RecordStore, SortCondition, SortOperator, SortOrder

from .conftest import RECORDS_TEST_TABLE as TABLE

pytestmark = pytest.mark.integration


def _seed(store: RecordStore, pk: str, sks: list[str]) -> None:
    for sk in sks:
        assert store.put(TABLE, {"pk": pk, "sk": sk, "value": sk}).is_success


def _sks(store: RecordStore, spec: RecordQuery) -> list[str]:
    result = store.query(TABLE, spec)
    assert result.is_success
    return [item["sk"] for item in result.data]


class TestFullKeyWrites:
    """Items are identified by the full key: partition plus sort attribute."""

    def test_put_overwrites_item_with_same_full_key(self, any_record_store: RecordStore) -> None:
        any_record_store.put(TABLE, {"pk": "a", "sk": "1", "value": "first"})
        any_record_store.put(TABLE, {"pk": "a", "sk": "1", "value": "second"})

        result = any_record_store.query(TABLE, RecordQuery(partition="a"))

        assert result.is_success
        assert [item["value"] for item in result.data] == ["second"]

    def test_get_returns_item_by_full_key(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, "a", ["1", "2"])

        result = any_record_store.get(TABLE, {"pk": "a", "sk": "2"})

        assert result.is_success
        assert result.data["value"] == "2"

    def test_get_missing_key_returns_not_found(self, any_record_store: RecordStore) -> None:
        result = any_record_store.get(TABLE, {"pk": "missing", "sk": "missing"})

        assert result.status == OperationStatus.NOT_FOUND

    def test_delete_removes_only_the_full_key(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, "a", ["1", "2"])

        assert any_record_store.delete(TABLE, {"pk": "a", "sk": "1"}).is_success

        assert any_record_store.get(TABLE, {"pk": "a", "sk": "1"}).status == OperationStatus.NOT_FOUND
        assert any_record_store.get(TABLE, {"pk": "a", "sk": "2"}).is_success

    def test_delete_of_missing_item_succeeds(self, any_record_store: RecordStore) -> None:
        assert any_record_store.delete(TABLE, {"pk": "missing", "sk": "missing"}).is_success


class TestPutIfNotExists:
    """The conditional create guards the full key, not just the partition."""

    def test_first_call_creates_item(self, any_record_store: RecordStore) -> None:
        result = any_record_store.put_if_not_exists(TABLE, {"pk": "a", "sk": "1"})

        assert result.is_success
        assert result.data is True

    def test_same_full_key_is_rejected_and_kept(self, any_record_store: RecordStore) -> None:
        any_record_store.put_if_not_exists(TABLE, {"pk": "a", "sk": "1", "value": "first"})

        result = any_record_store.put_if_not_exists(TABLE, {"pk": "a", "sk": "1", "value": "second"})

        assert result.is_success
        assert result.data is False
        assert any_record_store.get(TABLE, {"pk": "a", "sk": "1"}).data["value"] == "first"

    def test_new_sort_key_under_existing_partition_is_created(self, any_record_store: RecordStore) -> None:
        any_record_store.put_if_not_exists(TABLE, {"pk": "a", "sk": "1"})

        result = any_record_store.put_if_not_exists(TABLE, {"pk": "a", "sk": "2"})

        assert result.is_success
        assert result.data is True

    def test_a_created_item_reads_back_exactly_as_written(self, any_record_store: RecordStore) -> None:
        """The store's own bookkeeping attributes never reach a reader."""
        item = {"pk": "a", "sk": "1", "value": "first"}
        any_record_store.put_if_not_exists(TABLE, item)

        assert any_record_store.get(TABLE, {"pk": "a", "sk": "1"}).data == item
        assert any_record_store.query(TABLE, RecordQuery(partition="a")).data == [item]

    @pytest.mark.parametrize("operation", ["put", "put_if_not_exists"])
    def test_a_reserved_attribute_name_is_refused(self, any_record_store: RecordStore, operation: str) -> None:
        with pytest.raises(ValueError, match="reserved"):
            getattr(any_record_store, operation)(TABLE, {"pk": "a", "sk": "1", "_rs_write_token": "forged"})

        assert any_record_store.get(TABLE, {"pk": "a", "sk": "1"}).status == OperationStatus.NOT_FOUND


class TestKeyConditions:
    """Partition equality plus an optional eq, lt or begins_with sort condition."""

    def test_partition_equality_returns_only_that_partition_in_sort_order(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, "a", ["2", "1", "3"])
        _seed(any_record_store, "b", ["1"])

        assert _sks(any_record_store, RecordQuery(partition="a")) == ["1", "2", "3"]

    def test_empty_partition_returns_no_items(self, any_record_store: RecordStore) -> None:
        assert _sks(any_record_store, RecordQuery(partition="nobody")) == []

    def test_eq_matches_one_sort_key(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, "a", ["1", "2"])

        spec = RecordQuery(partition="a", sort=SortCondition(SortOperator.EQ, "2"))

        assert _sks(any_record_store, spec) == ["2"]

    def test_lt_is_exclusive(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, "a", ["2026-01-01", "2026-01-02", "2026-01-03"])

        spec = RecordQuery(partition="a", sort=SortCondition(SortOperator.LT, "2026-01-02"))

        assert _sks(any_record_store, spec) == ["2026-01-01"]

    def test_begins_with_matches_prefix(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, "a", ["DECISION#2", "REQUEST", "DECISION#1", "AUDIT#1"])

        spec = RecordQuery(partition="a", sort=SortCondition(SortOperator.BEGINS_WITH, "DECISION#"))

        assert _sks(any_record_store, spec) == ["DECISION#1", "DECISION#2"]


class TestOrderAndLimit:
    """Results follow the sort key in the requested order; limit caps the total."""

    def test_descending_order(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, "a", ["1", "2", "3"])

        assert _sks(any_record_store, RecordQuery(partition="a", order=SortOrder.DESC)) == ["3", "2", "1"]

    def test_limit_caps_total_items(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, "a", ["1", "2", "3"])

        assert _sks(any_record_store, RecordQuery(partition="a", limit=2)) == ["1", "2"]

    def test_descending_with_limit_returns_newest(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, "a", ["1", "2", "3"])

        spec = RecordQuery(partition="a", order=SortOrder.DESC, limit=1)

        assert _sks(any_record_store, spec) == ["3"]

    @pytest.mark.parametrize("limit", [3, 10])
    def test_limit_at_or_above_count_returns_everything(self, any_record_store: RecordStore, limit: int) -> None:
        _seed(any_record_store, "a", ["1", "2", "3"])

        assert _sks(any_record_store, RecordQuery(partition="a", limit=limit)) == ["1", "2", "3"]


class TestIndexQueries:
    """A logical index name resolves to the index key layout declared on the table."""

    def _seed_events(self, store: RecordStore) -> None:
        store.put(TABLE, {"pk": "r1", "sk": "1", "user": "alice", "timestamp": "2026-01-01"})
        store.put(TABLE, {"pk": "r2", "sk": "1", "user": "alice", "timestamp": "2026-01-03"})
        store.put(TABLE, {"pk": "r3", "sk": "1", "user": "bob", "timestamp": "2026-01-02"})
        store.put(TABLE, {"pk": "r4", "sk": "1", "value": "no index attributes"})

    def test_index_query_filters_on_index_partition(self, any_record_store: RecordStore) -> None:
        self._seed_events(any_record_store)

        result = any_record_store.query(TABLE, RecordQuery(partition="alice", index="by_user", order=SortOrder.DESC))

        assert result.is_success
        assert [item["pk"] for item in result.data] == ["r2", "r1"]

    def test_index_sort_condition_uses_reserved_word_attribute(self, any_record_store: RecordStore) -> None:
        self._seed_events(any_record_store)

        spec = RecordQuery(
            partition="alice",
            index="by_user",
            sort=SortCondition(SortOperator.LT, "2026-01-02"),
        )
        result = any_record_store.query(TABLE, spec)

        assert result.is_success
        assert [item["pk"] for item in result.data] == ["r1"]

    def test_unknown_index_raises(self, any_record_store: RecordStore) -> None:
        with pytest.raises(ValueError, match="by_nothing"):
            any_record_store.query(TABLE, RecordQuery(partition="alice", index="by_nothing"))
