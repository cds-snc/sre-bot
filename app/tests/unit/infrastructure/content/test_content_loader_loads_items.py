"""Behaviour of the content loader on well-formed content, over real files in a temporary root.

No collaborator is stubbed: a kind and its files are written under ``tmp_path`` and read back.
"""

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from infrastructure.content.loader import ContentLoader
from tests.factories.content import GADGETS, WIDGETS, Widget, widget_text, write_item

pytestmark = pytest.mark.unit


def _loader(root: Path) -> ContentLoader:
    return ContentLoader(root, max_file_bytes=16_384, max_items_per_kind=200)


def test_items_of_two_kinds_load_by_id_including_from_nested_folders(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "first.yaml", widget_text("first", "One"))
    write_item(tmp_path, WIDGETS, "team-a/deep/second.yaml", widget_text("second", "Two"))
    write_item(tmp_path, GADGETS, "gadget.yaml", widget_text("gadget", "Three", kind="probe/gadgets"))
    loader = _loader(tmp_path)
    loader.register(WIDGETS)
    loader.register(GADGETS)

    catalogue = loader.load()

    assert dict(catalogue.items(WIDGETS)) == {"first": Widget("first", "One"), "second": Widget("second", "Two")}
    assert dict(catalogue.items(GADGETS)) == {"gadget": Widget("gadget", "Three")}


def test_loaded_items_are_frozen_and_the_mapping_is_read_only(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "first.yaml", widget_text("first"))
    loader = _loader(tmp_path)
    loader.register(WIDGETS)

    items = loader.load().items(WIDGETS)

    with pytest.raises(FrozenInstanceError):
        items["first"].title = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        items["other"] = items["first"]  # type: ignore[index]


def test_only_registered_kinds_directories_are_read(tmp_path: Path) -> None:
    write_item(tmp_path, WIDGETS, "first.yaml", widget_text("first"))
    write_item(tmp_path, GADGETS, "broken.yaml", "not: [valid")
    loader = _loader(tmp_path)
    loader.register(WIDGETS)

    catalogue = loader.load()

    assert set(catalogue.items(WIDGETS)) == {"first"}
    assert dict(catalogue.items(GADGETS)) == {}


def test_no_registered_kind_reads_nothing_even_when_the_root_is_missing(tmp_path: Path) -> None:
    catalogue = _loader(tmp_path / "missing").load()

    assert dict(catalogue.items(WIDGETS)) == {}


def test_a_registered_optional_kind_with_a_missing_root_loads_empty(tmp_path: Path) -> None:
    loader = _loader(tmp_path / "missing")
    loader.register(WIDGETS)

    assert dict(loader.load().items(WIDGETS)) == {}


def test_registering_a_kind_twice_is_refused(tmp_path: Path) -> None:
    loader = _loader(tmp_path)
    loader.register(WIDGETS)

    with pytest.raises(ValueError, match="probe/widgets"):
        loader.register(WIDGETS)
