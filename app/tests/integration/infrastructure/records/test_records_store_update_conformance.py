"""Update conformance suite shared by the in-memory fake and the DynamoDB store.

Every case but one runs against both implementations through the
parametrized ``any_record_store`` fixture: set, remove and increment
changes, mixed change sets applied in one call, the existence requirement,
the optional equality guard, validation errors, sparse-index exclusion
after a remove, and sequential increment totals. Threaded increments run
on the fake only (see ``TestIncrementTotals``). Results are read back
through ``get`` or ``query`` so the assertions check stored state, not
only the returned value.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from contracts.operations.status import OperationStatus
from infrastructure.records.in_memory import InMemoryRecordStore
from infrastructure.records.protocol import (
    IncrementAttribute,
    RecordQuery,
    RecordStore,
    RemoveAttribute,
    SetAttribute,
)

from .conftest import RECORDS_TEST_TABLE as TABLE

pytestmark = pytest.mark.integration

KEY = {"pk": "a", "sk": "1"}


def _seed(store: RecordStore, **attributes: Any) -> None:
    assert store.put(TABLE, {**KEY, **attributes}).is_success


def _stored(store: RecordStore) -> dict[str, Any]:
    result = store.get(TABLE, KEY)
    assert result.is_success
    return dict(result.data)


class TestChanges:
    """Each change kind applies to an existing item and returns the full updated item."""

    def test_set_adds_and_overwrites_attributes(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, status="new", owner="x")

        result = any_record_store.update(TABLE, KEY, [SetAttribute("status", "open"), SetAttribute("title", "t")])

        assert result.is_success
        assert result.data == {**KEY, "status": "open", "owner": "x", "title": "t"}
        assert _stored(any_record_store) == result.data

    @pytest.mark.parametrize("value", [False, 0, ""])
    def test_set_stores_falsy_values(self, any_record_store: RecordStore, value: Any) -> None:
        _seed(any_record_store, field="x")

        any_record_store.update(TABLE, KEY, [SetAttribute("field", value)])

        assert _stored(any_record_store)["field"] == value

    def test_remove_drops_the_attribute(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, status="open", open_since="2026")

        result = any_record_store.update(TABLE, KEY, [RemoveAttribute("open_since")])

        assert result.is_success
        assert _stored(any_record_store) == {**KEY, "status": "open"}

    def test_remove_of_the_last_non_key_attribute_keeps_the_item(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, status="open")

        assert any_record_store.update(TABLE, KEY, [RemoveAttribute("status")]).is_success

        assert _stored(any_record_store) == KEY

    def test_remove_of_an_absent_attribute_succeeds(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, status="open")

        result = any_record_store.update(TABLE, KEY, [RemoveAttribute("missing")])

        assert result.is_success
        assert _stored(any_record_store) == {**KEY, "status": "open"}

    @pytest.mark.parametrize(("start", "delta", "end"), [(5, 3, 8), (5, -7, -2), (5, 0, 5)])
    def test_increment_adds_the_delta(self, any_record_store: RecordStore, start: int, delta: int, end: int) -> None:
        _seed(any_record_store, count=start)

        result = any_record_store.update(TABLE, KEY, [IncrementAttribute("count", delta)])

        assert result.is_success
        assert result.data["count"] == end
        assert _stored(any_record_store)["count"] == end

    def test_increment_of_an_absent_attribute_starts_at_zero(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store)

        result = any_record_store.update(TABLE, KEY, [IncrementAttribute("count", 4)])

        assert result.is_success
        assert _stored(any_record_store)["count"] == 4

    def test_mixed_changes_apply_in_one_call(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, status="open", open_since="2026", count=1)

        result = any_record_store.update(
            TABLE,
            KEY,
            [SetAttribute("status", "closed"), RemoveAttribute("open_since"), IncrementAttribute("count", 1)],
        )

        assert result.is_success
        assert _stored(any_record_store) == {**KEY, "status": "closed", "count": 2}


class TestExistence:
    """Update never creates an item."""

    def test_missing_item_is_not_found_and_not_created(self, any_record_store: RecordStore) -> None:
        result = any_record_store.update(TABLE, KEY, [SetAttribute("status", "open")])

        assert result.status == OperationStatus.NOT_FOUND
        assert any_record_store.get(TABLE, KEY).status == OperationStatus.NOT_FOUND

    def test_missing_item_with_guard_is_not_found(self, any_record_store: RecordStore) -> None:
        result = any_record_store.update(TABLE, KEY, [SetAttribute("status", "open")], expected={"status": "new"})

        assert result.status == OperationStatus.NOT_FOUND


class TestGuard:
    """The expected guard is checked atomically with the change set."""

    def test_guard_that_holds_applies_the_changes(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, status="open", count=1)

        result = any_record_store.update(TABLE, KEY, [SetAttribute("status", "closed")], expected={"status": "open", "count": 1})

        assert result.is_success
        assert result.data is not None
        assert _stored(any_record_store)["status"] == "closed"

    def test_guard_that_fails_writes_nothing_and_is_not_an_error(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, status="open", open_since="2026", count=1)

        result = any_record_store.update(
            TABLE,
            KEY,
            [SetAttribute("status", "closed"), RemoveAttribute("open_since"), IncrementAttribute("count", 1)],
            expected={"status": "new"},
        )

        assert result.is_success
        assert result.data is None
        assert _stored(any_record_store) == {**KEY, "status": "open", "open_since": "2026", "count": 1}

    def test_guard_none_means_the_attribute_is_absent(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, status="open")

        assigned = any_record_store.update(TABLE, KEY, [SetAttribute("owner", "x")], expected={"owner": None})
        reassigned = any_record_store.update(TABLE, KEY, [SetAttribute("owner", "y")], expected={"owner": None})

        assert assigned.data is not None
        assert reassigned.is_success
        assert reassigned.data is None
        assert _stored(any_record_store)["owner"] == "x"


class TestValidation:
    """Caller programming errors raise before any write."""

    def test_change_on_a_key_attribute_raises(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store)

        with pytest.raises(ValueError, match="key attribute"):
            any_record_store.update(TABLE, KEY, [SetAttribute("sk", "2")])

    def test_guard_on_a_key_attribute_raises(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store)

        with pytest.raises(ValueError, match="key attribute"):
            any_record_store.update(TABLE, KEY, [SetAttribute("status", "x")], expected={"pk": "a"})

    def test_partial_key_raises(self, any_record_store: RecordStore) -> None:
        with pytest.raises(ValueError, match="key"):
            any_record_store.update(TABLE, {"pk": "a"}, [SetAttribute("status", "x")])

    def test_empty_change_set_raises(self, any_record_store: RecordStore) -> None:
        with pytest.raises(ValueError, match="at least one change"):
            any_record_store.update(TABLE, KEY, [])


class TestSparseIndex:
    """An item without an index's key attributes drops out of that index."""

    def test_removing_an_index_attribute_excludes_the_item(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, user="u1", timestamp="2026-01-01")
        assert len(any_record_store.query(TABLE, RecordQuery(partition="u1", index="by_user")).data) == 1

        any_record_store.update(TABLE, KEY, [RemoveAttribute("user")])

        result = any_record_store.query(TABLE, RecordQuery(partition="u1", index="by_user"))
        assert result.is_success
        assert result.data == []


class TestIncrementTotals:
    """Repeated increments are never lost.

    The threaded case runs on the in-memory fake only: moto's DynamoDB
    backend applies UpdateItem as an unlocked read-modify-write, so it loses
    increments under threads and cannot stand in for DynamoDB's atomicity.
    On both stores the same increments run sequentially; that DynamoDB sends
    a single UpdateItem with no read is asserted by the expression unit tests.
    """

    threads, per_thread = 8, 25
    total = per_thread * sum(range(1, threads + 1))

    def test_sequential_increments_sum_to_the_total_of_all_deltas(self, any_record_store: RecordStore) -> None:
        _seed(any_record_store, count=0)

        for delta in range(1, self.threads + 1):
            for _ in range(self.per_thread):
                assert any_record_store.update(TABLE, KEY, [IncrementAttribute("count", delta)]).is_success

        assert _stored(any_record_store)["count"] == self.total

    def test_concurrent_increments_on_the_fake_sum_to_the_total_of_all_deltas(self) -> None:
        store = InMemoryRecordStore()
        _seed(store, count=0)

        def increment_many(delta: int) -> None:
            for _ in range(self.per_thread):
                assert store.update(TABLE, KEY, [IncrementAttribute("count", delta)]).is_success

        with ThreadPoolExecutor(max_workers=self.threads) as pool:
            list(pool.map(increment_many, range(1, self.threads + 1)))

        assert _stored(store)["count"] == self.total
