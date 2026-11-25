"""Registration rules of a content kind: reserved owner names, name shape, versions, limits and the file model's fields."""

import pytest
from pydantic import ValidationError

from contracts.content import CONTENT_ID_PATTERN, ContentDocument, ContentKind
from tests.factories.content import WIDGETS, WidgetDocument, build_widget

pytestmark = pytest.mark.unit


def _kind(**overrides: object) -> ContentKind:
    fields = {"owner": "probe", "name": "widgets", "model": WidgetDocument, "build": build_widget, **overrides}
    return ContentKind(**fields)  # type: ignore[arg-type]


def test_the_key_is_owner_slash_name() -> None:
    assert WIDGETS.key == "probe/widgets"
    assert _kind(owner="incident.response").key == "incident.response/widgets"


@pytest.mark.parametrize("owner", ["schemas", "examples", "Bad", "has space", "", "a/b"])
def test_a_reserved_or_malformed_owner_is_refused(owner: str) -> None:
    with pytest.raises(ValueError, match="owner"):
        _kind(owner=owner)


@pytest.mark.parametrize("name", ["Widgets", "sender_kinds", "", "a/b", "-x"])
def test_a_malformed_kind_name_is_refused(name: str) -> None:
    with pytest.raises(ValueError, match="name"):
        _kind(name=name)


def test_a_plural_kebab_name_is_accepted() -> None:
    assert _kind(name="sender-kinds").key == "probe/sender-kinds"


@pytest.mark.parametrize("versions", [frozenset(), frozenset({0}), frozenset({-1, 1})])
def test_empty_or_non_positive_versions_are_refused(versions: frozenset[int]) -> None:
    with pytest.raises(ValueError, match="versions"):
        _kind(versions=versions)


@pytest.mark.parametrize("limit", [{"max_file_bytes": 0}, {"max_items": 0}])
def test_a_non_positive_kind_limit_is_refused(limit: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="positive"):
        _kind(**limit)


@pytest.mark.parametrize("item_id", ["a", "a1", "a_b-c", "0abc", "a" * 64])
def test_ids_matching_the_pattern_validate(item_id: str) -> None:
    assert ContentDocument(kind="p/k", version=1, id=item_id).id == item_id


@pytest.mark.parametrize("item_id", ["", "A", "-a", "_a", "a b", "a.b", "a" * 65, "../x"])
def test_ids_outside_the_pattern_are_refused(item_id: str) -> None:
    assert CONTENT_ID_PATTERN.fullmatch(item_id) is None
    with pytest.raises(ValidationError):
        ContentDocument(kind="p/k", version=1, id=item_id)
