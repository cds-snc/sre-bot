"""In-memory RecordStore implementation."""

from copy import deepcopy
from typing import Any

from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from infrastructure.records.protocol import (
    KeySchema,
    RecordQuery,
    RecordStore,
    RecordTable,
    SortCondition,
    SortOperator,
    SortOrder,
    resolve_query_key,
)

type _FullKey = tuple[Any, ...]


def _key_attributes(key: KeySchema) -> tuple[str, ...]:
    return (key.partition,) if key.sort is None else (key.partition, key.sort)


def _matches(value: Any, condition: SortCondition) -> bool:
    match condition.operator:
        case SortOperator.EQ:
            return bool(value == condition.value)
        case SortOperator.LT:
            return type(value) is type(condition.value) and value < condition.value
        case SortOperator.BEGINS_WITH:
            return isinstance(value, str) and value.startswith(str(condition.value))


class InMemoryRecordStore(RecordStore):
    """In-memory record store keyed by each table's full key.

    Mirrors the DynamoDB-backed store's semantics (overwrite on put,
    full-key conditional create, key-condition queries with sort order and a
    total limit) while keeping data in process memory for deterministic tests
    and development.
    """

    def __init__(self) -> None:
        self._tables: dict[str, dict[_FullKey, dict[str, Any]]] = {}

    def _full_key(self, table: RecordTable, item: dict[str, Any]) -> _FullKey | None:
        attributes = _key_attributes(table.key)
        if any(item.get(attribute) is None for attribute in attributes):
            return None
        return tuple(item[attribute] for attribute in attributes)

    @staticmethod
    def _missing_key(table: RecordTable) -> OperationResult:
        return OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message=f"Missing key attribute for {table.name}: {', '.join(_key_attributes(table.key))}",
        )

    @staticmethod
    def _not_found(table: RecordTable) -> OperationResult:
        return OperationResult.error(status=OperationStatus.NOT_FOUND, message=f"Item not found in {table.name}")

    def put(self, table: RecordTable, item: dict[str, Any]) -> OperationResult:
        full_key = self._full_key(table, item)
        if full_key is None:
            return self._missing_key(table)
        self._tables.setdefault(table.name, {})[full_key] = deepcopy(item)
        return OperationResult.success(data=None)

    def put_if_not_exists(self, table: RecordTable, item: dict[str, Any]) -> OperationResult:
        full_key = self._full_key(table, item)
        if full_key is None:
            return self._missing_key(table)
        records = self._tables.setdefault(table.name, {})
        if full_key in records:
            return OperationResult.success(data=False, message="Item already exists")
        records[full_key] = deepcopy(item)
        return OperationResult.success(data=True, message="Item created")

    def get(self, table: RecordTable, key: dict[str, Any]) -> OperationResult:
        full_key = self._full_key(table, key)
        item = self._tables.get(table.name, {}).get(full_key) if full_key is not None else None
        if item is None:
            return self._not_found(table)
        return OperationResult.success(data=deepcopy(item))

    def query(self, table: RecordTable, spec: RecordQuery) -> OperationResult:
        key = resolve_query_key(table, spec)
        required = _key_attributes(key)
        records = [
            item
            for item in self._tables.get(table.name, {}).values()
            if all(attribute in item for attribute in required) and item[key.partition] == spec.partition
        ]
        if spec.sort is not None and key.sort is not None:
            condition, sort_attribute = spec.sort, key.sort
            records = [item for item in records if _matches(item[sort_attribute], condition)]
        if key.sort is not None:
            sort_attribute = key.sort
            records.sort(key=lambda item: item[sort_attribute], reverse=spec.order is SortOrder.DESC)
        if spec.limit is not None:
            records = records[: spec.limit]
        return OperationResult.success(data=deepcopy(records))

    def delete(self, table: RecordTable, key: dict[str, Any]) -> OperationResult:
        full_key = self._full_key(table, key)
        if full_key is None:
            return self._missing_key(table)
        self._tables.get(table.name, {}).pop(full_key, None)
        return OperationResult.success(data=None)
