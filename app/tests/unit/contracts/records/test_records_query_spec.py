"""Tests for the records contract value types and key resolution.

Validates RecordQuery field checks, resolve_query_key outcomes for table
and index queries, RecordTable hashability, and that no vendor (DynamoDB)
vocabulary leaks into the Protocol surface.
"""

import inspect

import pytest

from contracts.records import (
    KeySchema,
    RecordIndex,
    RecordQuery,
    RecordStore,
    RecordTable,
    SortCondition,
    SortOperator,
    SortOrder,
    resolve_query_key,
    store,
)

pytestmark = pytest.mark.unit

TABLE = RecordTable(
    name="events",
    key=KeySchema(partition="resource_id", sort="sk"),
    indexes={
        "by_user": RecordIndex(physical_name="user-index", key=KeySchema(partition="user", sort="timestamp")),
        "by_correlation": RecordIndex(physical_name="correlation-index", key=KeySchema(partition="correlation_id")),
    },
)


class TestRecordQueryValidation:
    """RecordQuery rejects field combinations no backend can honour."""

    def test_defaults_are_ascending_and_unbounded(self) -> None:
        spec = RecordQuery(partition="a")

        assert spec.order is SortOrder.ASC
        assert spec.limit is None
        assert spec.sort is None
        assert spec.index is None

    def test_begins_with_requires_a_string_value(self) -> None:
        with pytest.raises(ValueError, match="begins_with"):
            RecordQuery(partition="a", sort=SortCondition(SortOperator.BEGINS_WITH, 5))

    @pytest.mark.parametrize("limit", [0, -1])
    def test_limit_below_one_is_rejected(self, limit: int) -> None:
        with pytest.raises(ValueError, match="limit"):
            RecordQuery(partition="a", limit=limit)

    def test_limit_of_one_is_accepted(self) -> None:
        assert RecordQuery(partition="a", limit=1).limit == 1

    def test_only_operators_with_a_consumer_exist(self) -> None:
        assert {op.name for op in SortOperator} == {"EQ", "LT", "BEGINS_WITH"}


class TestResolveQueryKey:
    """resolve_query_key returns the effective key or fails loudly on a schema mismatch."""

    def test_table_query_uses_table_key(self) -> None:
        assert resolve_query_key(TABLE, RecordQuery(partition="a")) == TABLE.key

    def test_index_query_uses_index_key(self) -> None:
        key = resolve_query_key(TABLE, RecordQuery(partition="u", index="by_user"))

        assert key == KeySchema(partition="user", sort="timestamp")

    def test_unknown_index_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="by_nothing"):
            resolve_query_key(TABLE, RecordQuery(partition="a", index="by_nothing"))

    def test_sort_condition_on_key_without_sort_attribute_is_rejected(self) -> None:
        spec = RecordQuery(
            partition="c",
            index="by_correlation",
            sort=SortCondition(SortOperator.EQ, "x"),
        )

        with pytest.raises(ValueError, match="sort"):
            resolve_query_key(TABLE, spec)


class TestRecordTable:
    """RecordTable is an immutable, hashable declaration."""

    def test_table_is_hashable(self) -> None:
        assert hash(TABLE) == hash(TABLE)

    def test_indexes_default_to_empty(self) -> None:
        assert dict(RecordTable(name="t", key=KeySchema(partition="pk")).indexes) == {}

    def test_indexes_cannot_be_mutated(self) -> None:
        with pytest.raises(TypeError):
            TABLE.indexes["new"] = RecordIndex(physical_name="x", key=KeySchema(partition="p"))  # type: ignore[index]


class TestProtocolSurface:
    """Every RecordStore method takes a RecordTable and no vendor parameters."""

    @pytest.mark.parametrize(
        ("method", "params"),
        [
            ("put", ["self", "table", "item"]),
            ("put_if_not_exists", ["self", "table", "item"]),
            ("get", ["self", "table", "key"]),
            ("query", ["self", "table", "spec"]),
            ("delete", ["self", "table", "key"]),
        ],
    )
    def test_method_parameters(self, method: str, params: list[str]) -> None:
        signature = inspect.signature(getattr(RecordStore, method))

        assert list(signature.parameters) == params
        assert signature.parameters["table"].annotation is RecordTable

    def test_protocol_module_has_no_vendor_vocabulary(self) -> None:
        source = inspect.getsource(store)

        for term in (
            "KeyConditionExpression",
            "ExpressionAttribute",
            "ScanIndexForward",
            "UpdateExpression",
            "ConditionExpression",
            "attribute_not_exists",
            "boto",
            "dynamodb",
        ):
            assert term not in source
