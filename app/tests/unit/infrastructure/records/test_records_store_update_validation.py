"""Unit tests for the shared update validation helper.

``validate_record_update`` rejects caller programming errors before any
store does I/O, so both stores raise the same ``ValueError`` for the same
mistake. Each case builds the smallest input that triggers one rule.
"""

import pytest

from infrastructure.records.protocol import (
    IncrementAttribute,
    KeySchema,
    RecordChange,
    RecordTable,
    RemoveAttribute,
    SetAttribute,
    validate_record_update,
)

TABLE = RecordTable(name="t", key=KeySchema(partition="pk", sort="sk"))
KEY = {"pk": "a", "sk": "1"}

pytestmark = pytest.mark.unit


def test_valid_update_passes() -> None:
    changes: list[RecordChange] = [
        SetAttribute("status", "open"),
        RemoveAttribute("open_since"),
        IncrementAttribute("count", -2),
    ]

    validate_record_update(TABLE, KEY, changes, {"status": "new", "owner": None})


@pytest.mark.parametrize(
    "key",
    [{"pk": "a"}, {"pk": "a", "sk": "1", "extra": "x"}, {"pk": "a", "sk": None}, {}],
)
def test_key_not_matching_table_key_is_rejected(key: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="key"):
        validate_record_update(TABLE, key, [SetAttribute("status", "open")], None)


@pytest.mark.parametrize(
    "change",
    [SetAttribute("pk", "b"), RemoveAttribute("sk"), IncrementAttribute("sk", 1)],
)
def test_change_on_key_attribute_is_rejected(change: RecordChange) -> None:
    with pytest.raises(ValueError, match="key attribute"):
        validate_record_update(TABLE, KEY, [change], None)


def test_guard_on_key_attribute_is_rejected() -> None:
    with pytest.raises(ValueError, match="key attribute"):
        validate_record_update(TABLE, KEY, [SetAttribute("status", "open")], {"pk": "a"})


def test_empty_change_set_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one change"):
        validate_record_update(TABLE, KEY, [], None)


def test_attribute_named_by_two_changes_is_rejected() -> None:
    with pytest.raises(ValueError, match="more than one change"):
        validate_record_update(TABLE, KEY, [SetAttribute("status", "open"), RemoveAttribute("status")], None)


@pytest.mark.parametrize("delta", [True, 1.5, "1"])
def test_non_integer_increment_delta_is_rejected(delta: object) -> None:
    with pytest.raises(ValueError, match="integer"):
        validate_record_update(TABLE, KEY, [IncrementAttribute("count", delta)], None)  # type: ignore[arg-type]
