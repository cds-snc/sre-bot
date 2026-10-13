"""Protocol contract for the record store.

Defines the runtime-checkable interface consumed by feature packages and
infrastructure services, and the vendor-neutral value types it speaks:
a table declares its key layout once (``RecordTable``) and reads describe
what they want (``RecordQuery``), never how a backend expresses it.
Concrete implementations can vary by backing store.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from contracts.operations.result import OperationResult

type KeyValue = str | int


@dataclass(frozen=True, slots=True)
class KeySchema:
    """Key attribute names: a partition attribute and an optional sort attribute."""

    partition: str
    sort: str | None = None


@dataclass(frozen=True, slots=True)
class RecordIndex:
    """A secondary index: the backend's own index name and its key layout."""

    physical_name: str
    key: KeySchema


@dataclass(frozen=True, slots=True)
class RecordTable:
    """A table's name and key layout, declared once by the repository that owns it.

    ``indexes`` maps a logical name (for example ``"by_user"``) to the
    index it stands for, so callers never name a backend index directly.
    """

    name: str
    key: KeySchema
    indexes: Mapping[str, RecordIndex] = field(default_factory=lambda: MappingProxyType({}), hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "indexes", MappingProxyType(dict(self.indexes)))


class SortOperator(StrEnum):
    """Sort-key comparisons with a consumer today.

    ``gt`` and ``between`` are deferred until a caller needs them; ``between``
    is what the audit trail's unimplemented ``end_time`` bound would use.
    ``begins_with`` lowers to a key range on stores without a prefix
    operator (Azure Table, Firestore), ``STARTSWITH`` on Cosmos DB and
    ``LIKE 'prefix%'`` on Postgres.
    """

    EQ = "eq"
    LT = "lt"
    BEGINS_WITH = "begins_with"


class SortOrder(StrEnum):
    """Result order on the effective sort key."""

    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class SortCondition:
    """A comparison applied to the sort attribute."""

    operator: SortOperator
    value: KeyValue


@dataclass(frozen=True, slots=True)
class RecordQuery:
    """A key-condition read: partition equality plus an optional sort condition.

    Attributes:
        partition: Value the partition attribute must equal.
        sort: Optional condition on the sort attribute.
        index: Optional logical index name declared on the table.
        limit: Maximum number of items returned in total; ``None`` returns every match.
        order: Order of results on the sort attribute.
    """

    partition: KeyValue
    sort: SortCondition | None = None
    index: str | None = None
    limit: int | None = None
    order: SortOrder = SortOrder.ASC

    def __post_init__(self) -> None:
        if self.sort is not None and self.sort.operator is SortOperator.BEGINS_WITH and not isinstance(self.sort.value, str):
            raise ValueError("begins_with requires a string value")
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit must be at least 1")


def resolve_query_key(table: RecordTable, spec: RecordQuery) -> KeySchema:
    """Return the key layout a query runs against: the table's or its index's.

    Raises:
        ValueError: The index is not declared on the table, or a sort
            condition targets a key layout without a sort attribute. Both are
            caller programming errors, not runtime backend failures.
    """
    if spec.index is None:
        key = table.key
    elif spec.index in table.indexes:
        key = table.indexes[spec.index].key
    else:
        raise ValueError(f"index {spec.index!r} is not declared on table {table.name!r}")
    if spec.sort is not None and key.sort is None:
        raise ValueError(f"sort condition given but the key of {table.name!r} has no sort attribute")
    return key


@runtime_checkable
class RecordStore(Protocol):
    """Record operations abstracted over the backing store."""

    def put(self, table: RecordTable, item: dict[str, Any]) -> OperationResult: ...

    def put_if_not_exists(self, table: RecordTable, item: dict[str, Any]) -> OperationResult: ...

    def get(self, table: RecordTable, key: dict[str, Any]) -> OperationResult: ...

    def query(self, table: RecordTable, spec: RecordQuery) -> OperationResult: ...

    def delete(self, table: RecordTable, key: dict[str, Any]) -> OperationResult: ...
