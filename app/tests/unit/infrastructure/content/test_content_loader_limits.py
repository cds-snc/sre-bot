"""Behaviour of the content loader's size and count limits, over real files in a temporary root."""

from dataclasses import replace
from pathlib import Path

import pytest

from contracts.content import ContentKind, ContentLoadError
from infrastructure.content.loader import ContentLoader
from tests.factories.content import WIDGETS, widget_text, write_item

pytestmark = pytest.mark.unit


def _load(root: Path, kind: ContentKind, *, max_file_bytes: int = 16_384, max_items: int = 200):
    loader = ContentLoader(root, max_file_bytes=max_file_bytes, max_items_per_kind=max_items)
    loader.register(kind)
    return loader.load()


def _problems(root: Path, kind: ContentKind, **limits: int):
    with pytest.raises(ContentLoadError) as raised:
        _load(root, kind, **limits)
    return raised.value.problems


def test_a_file_at_exactly_the_size_limit_loads_and_one_byte_over_is_refused(tmp_path: Path) -> None:
    text = widget_text("a")
    write_item(tmp_path, WIDGETS, "a.yaml", text)
    size = len(text.encode())

    assert set(_load(tmp_path, WIDGETS, max_file_bytes=size).items(WIDGETS)) == {"a"}
    (problem,) = _problems(tmp_path, WIDGETS, max_file_bytes=size - 1)
    assert (problem.file, "bytes" in problem.message) == ("probe/widgets/a.yaml", True)


def test_a_kind_may_lower_the_file_size_limit_but_not_raise_it(tmp_path: Path) -> None:
    text = widget_text("a")
    write_item(tmp_path, WIDGETS, "a.yaml", text)
    size = len(text.encode())

    assert _problems(tmp_path, replace(WIDGETS, max_file_bytes=size - 1))
    assert set(_load(tmp_path, replace(WIDGETS, max_file_bytes=size * 10), max_file_bytes=size).items(WIDGETS)) == {"a"}
    assert _problems(tmp_path, replace(WIDGETS, max_file_bytes=size * 10), max_file_bytes=size - 1)


def test_items_over_the_count_limit_are_refused_naming_the_kind(tmp_path: Path) -> None:
    for name in ("a", "b", "c"):
        write_item(tmp_path, WIDGETS, f"{name}.yaml", widget_text(name))

    assert set(_load(tmp_path, WIDGETS, max_items=3).items(WIDGETS)) == {"a", "b", "c"}
    (problem,) = _problems(tmp_path, WIDGETS, max_items=2)
    assert problem.kind == "probe/widgets"


def test_a_kind_may_lower_the_count_limit_but_not_raise_it(tmp_path: Path) -> None:
    for name in ("a", "b"):
        write_item(tmp_path, WIDGETS, f"{name}.yaml", widget_text(name))

    assert _problems(tmp_path, replace(WIDGETS, max_items=1))
    assert _problems(tmp_path, replace(WIDGETS, max_items=50), max_items=1)


def test_a_required_kind_with_no_items_is_refused_naming_the_kind(tmp_path: Path) -> None:
    (problem,) = _problems(tmp_path, replace(WIDGETS, required=True))

    assert problem.kind == "probe/widgets"
    assert "required" in problem.message


def test_an_optional_kind_with_no_items_loads_empty(tmp_path: Path) -> None:
    assert dict(_load(tmp_path, WIDGETS).items(WIDGETS)) == {}
