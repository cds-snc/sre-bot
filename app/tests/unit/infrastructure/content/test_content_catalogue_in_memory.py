"""The in-memory content catalogue honours the ContentCatalogue contract; no collaborators."""

import pytest

from infrastructure.content.in_memory import InMemoryContentCatalogue
from tests.factories.content import GADGETS, WIDGETS, Widget

pytestmark = pytest.mark.unit


def test_a_kind_with_no_items_reads_empty() -> None:
    assert dict(InMemoryContentCatalogue().items(WIDGETS)) == {}


def test_added_items_are_read_back_by_kind_and_id() -> None:
    catalogue = InMemoryContentCatalogue()
    catalogue.add(WIDGETS, "a", Widget("a", "One"))
    catalogue.add(GADGETS, "g", Widget("g", "Two"))

    assert dict(catalogue.items(WIDGETS)) == {"a": Widget("a", "One")}
    assert dict(catalogue.items(GADGETS)) == {"g": Widget("g", "Two")}


def test_the_returned_mapping_is_read_only() -> None:
    catalogue = InMemoryContentCatalogue()

    with pytest.raises(TypeError):
        catalogue.items(WIDGETS)["x"] = Widget("x", "X")  # type: ignore[index]
