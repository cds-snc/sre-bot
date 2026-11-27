"""In-memory content catalogue for consumer tests."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from contracts.content import ContentCatalogue, ContentKind


class InMemoryContentCatalogue(ContentCatalogue):
    """A catalogue a test fills with ready-built items; it honours the ``ContentCatalogue`` contract."""

    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def add[T](self, kind: ContentKind[Any, T], item_id: str, item: T) -> None:
        """Add one item of ``kind`` under ``item_id``."""
        self._items.setdefault(kind.key, {})[item_id] = item

    def items[T](self, kind: ContentKind[Any, T]) -> Mapping[str, T]:
        """Return a read-only view of the kind's items, empty when none were added."""
        return MappingProxyType(self._items.get(kind.key, {}))
