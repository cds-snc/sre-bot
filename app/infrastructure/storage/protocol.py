"""Protocol contract for storage services.

Defines the runtime-checkable interface consumed by feature packages and
infrastructure services. Concrete implementations can vary by backing store.
"""

from typing import Any, Protocol, runtime_checkable

from infrastructure.operations.result import OperationResult


@runtime_checkable
class StorageService(Protocol):
    """Storage operations abstracted over the backing store."""

    def put(self, table: str, item: dict[str, Any]) -> OperationResult: ...

    def put_if_not_exists(
        self,
        table: str,
        item: dict[str, Any],
        pk_attribute: str,
    ) -> OperationResult: ...

    def get(self, table: str, key: dict[str, Any]) -> OperationResult: ...

    def query(
        self,
        table: str,
        key_condition: str,
        expression_values: dict[str, Any],
        **kwargs: Any,
    ) -> OperationResult: ...

    def delete(self, table: str, key: dict[str, Any]) -> OperationResult: ...
