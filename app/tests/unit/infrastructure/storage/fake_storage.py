"""In-memory fake storage implementation for tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus


class FakeStorageService:
    """Simple in-memory storage fake that follows StorageService protocol."""

    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}

    def put(self, table: str, item: dict[str, Any]) -> OperationResult:
        records = self._tables.setdefault(table, [])
        records.append(deepcopy(item))
        return OperationResult.success(data=None)

    def put_if_not_exists(
        self,
        table: str,
        item: dict[str, Any],
        pk_attribute: str,
    ) -> OperationResult:
        if pk_attribute not in item:
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message=f"Missing primary key attribute: {pk_attribute}",
            )

        key_value = item[pk_attribute]
        records = self._tables.setdefault(table, [])
        for existing in records:
            if existing.get(pk_attribute) == key_value:
                return OperationResult.success(data=False)

        records.append(deepcopy(item))
        return OperationResult.success(data=True)

    def get(self, table: str, key: dict[str, Any]) -> OperationResult:
        records = self._tables.get(table, [])
        for item in records:
            if all(item.get(k) == v for k, v in key.items()):
                return OperationResult.success(data=deepcopy(item))

        return OperationResult.error(
            status=OperationStatus.NOT_FOUND,
            message=f"Item not found in {table}",
        )

    def query(
        self,
        table: str,
        key_condition: str,
        expression_values: dict[str, Any],
        **kwargs: Any,
    ) -> OperationResult:
        records = list(self._tables.get(table, []))

        pk_value = expression_values.get(":pk")
        if pk_value is not None:
            records = [item for item in records if item.get("PK") == pk_value]

        prefix_value = expression_values.get(":prefix")
        if prefix_value is not None:
            records = [
                item for item in records if isinstance(item.get("SK"), str) and str(item.get("SK")).startswith(str(prefix_value))
            ]

        scan_forward = kwargs.get("ScanIndexForward", True)
        if scan_forward is False:
            records = list(reversed(records))

        limit = kwargs.get("Limit")
        if isinstance(limit, int):
            records = records[:limit]

        return OperationResult.success(data=deepcopy(records))

    def delete(self, table: str, key: dict[str, Any]) -> OperationResult:
        records = self._tables.get(table, [])
        for index, item in enumerate(records):
            if all(item.get(k) == v for k, v in key.items()):
                records.pop(index)
                return OperationResult.success(data=None)

        return OperationResult.error(
            status=OperationStatus.NOT_FOUND,
            message=f"Item not found in {table}",
        )
