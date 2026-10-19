"""Protocol contract for the record store.

Defines the runtime-checkable interface consumed by feature packages and
infrastructure services, and the vendor-neutral value types it speaks:
a table declares its key layout once (``RecordTable``) and reads describe
what they want (``RecordQuery``), never how a backend expresses it.
Writes to an existing item describe their changes (``RecordChange``) and
an optional equality guard, never a backend update expression.
Concrete implementations can vary by backing store.
"""

from collections.abc import Mapping, Sequence
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


@dataclass(frozen=True, slots=True)
class SetAttribute:
    """Set a non-key attribute to a value, adding it when absent."""

    attribute: str
    value: Any


@dataclass(frozen=True, slots=True)
class RemoveAttribute:
    """Remove a non-key attribute; removing an absent attribute is a no-op."""

    attribute: str


@dataclass(frozen=True, slots=True)
class IncrementAttribute:
    """Add an integer delta to a numeric attribute; an absent attribute counts as 0."""

    attribute: str
    delta: int


type RecordChange = SetAttribute | RemoveAttribute | IncrementAttribute

type ExpectedValue = KeyValue | bool | None

# Attribute names under this prefix belong to the record stores, never to callers.
RESERVED_ATTRIBUTE_PREFIX = "_rs_"


def _check_attribute_name(attribute: str) -> None:
    if attribute.startswith(RESERVED_ATTRIBUTE_PREFIX):
        raise ValueError(f"attribute {attribute!r} uses the reserved prefix {RESERVED_ATTRIBUTE_PREFIX!r}")


def validate_record_item(item: Mapping[str, Any]) -> None:
    """Check that an item written by a caller names no reserved attribute.

    Raises:
        ValueError: An attribute name starts with ``RESERVED_ATTRIBUTE_PREFIX``,
            a caller programming error.
    """
    for attribute in item:
        _check_attribute_name(attribute)


def validate_record_update(
    table: RecordTable,
    key: Mapping[str, Any],
    changes: Sequence[RecordChange],
    expected: Mapping[str, ExpectedValue] | None,
) -> None:
    """Check an update's inputs against the table's key layout.

    Raises:
        ValueError: The key does not name exactly the table's key attributes,
            a change or guard entry targets a key attribute, the change set is
            empty, one attribute is named by more than one change, or an
            increment delta is not an ``int``, or a change or guard names a
            reserved attribute. All are caller programming errors, not
            runtime backend failures.
    """
    key_attributes = {table.key.partition} if table.key.sort is None else {table.key.partition, table.key.sort}
    if set(key) != key_attributes or any(key[attribute] is None for attribute in key_attributes):
        raise ValueError(f"key must name exactly the key attributes of {table.name!r}: {sorted(key_attributes)}")
    if not changes:
        raise ValueError("update requires at least one change")
    seen: set[str] = set()
    for change in changes:
        _check_attribute_name(change.attribute)
        if change.attribute in key_attributes:
            raise ValueError(f"change on key attribute {change.attribute!r}")
        if change.attribute in seen:
            raise ValueError(f"attribute {change.attribute!r} is named by more than one change")
        seen.add(change.attribute)
        if isinstance(change, IncrementAttribute) and type(change.delta) is not int:
            raise ValueError(f"increment delta for {change.attribute!r} must be an integer")
    for attribute in expected or {}:
        _check_attribute_name(attribute)
        if attribute in key_attributes:
            raise ValueError(f"guard on key attribute {attribute!r}")


@runtime_checkable
class RecordStore(Protocol):
    """Record operations abstracted over the backing store.

    Index semantics: an index query returns full items, like a table query
    (indexes are declared with every attribute projected), so a caller never
    follows it with a ``get``. An item missing any of an index's key
    attributes is excluded from that index's queries (sparse indexes), so
    removing an attribute takes the item out of the index. Index reads may be
    eventually consistent and index keys are not unique.

    ``update`` changes one existing item atomically and never creates one:

    - every change in the call applies together, or none does;
    - ``expected`` is an equality guard on non-key attributes, checked in the
      same atomic step; a ``None`` value means the attribute is absent;
    - an applied update returns ``success`` with the full updated item, a
      missing item returns ``NOT_FOUND``, and an unmet guard returns
      ``success`` with ``data=None`` and nothing written;
    - an increment is not idempotent: an SDK retry after a lost response may
      apply it twice, which is acceptable for counters.

    ``put_if_not_exists`` returns ``data=True`` only to the call that created
    the item, including when the SDK retried that call after a lost response,
    and ``data=False`` when the item already existed. A store may keep its own
    bookkeeping on items under ``RESERVED_ATTRIBUTE_PREFIX``; reads never
    return it, and an item, change or guard naming such an attribute raises
    ``ValueError``.

    Appending to a list attribute is deliberately not offered: a growing
    sequence, such as incident timeline entries, is stored as its own records
    in a separate table. A bounded full-table read is a separate operation,
    added with its first consumer.
    """

    def put(self, table: RecordTable, item: dict[str, Any]) -> OperationResult: ...

    def put_if_not_exists(self, table: RecordTable, item: dict[str, Any]) -> OperationResult: ...

    def get(self, table: RecordTable, key: dict[str, Any]) -> OperationResult: ...

    def query(self, table: RecordTable, spec: RecordQuery) -> OperationResult: ...

    def delete(self, table: RecordTable, key: dict[str, Any]) -> OperationResult: ...

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Mapping[str, ExpectedValue] | None = None,
    ) -> OperationResult: ...
