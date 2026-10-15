"""Behavior tests for the reserved attribute names of the records contract.

Attribute names under the reserved prefix belong to the record stores (the
write token of put_if_not_exists lives there), so a caller may not write or
guard them. The checks are pure and raise ValueError for a caller error.
"""

import pytest

from contracts.records import (
    RESERVED_ATTRIBUTE_PREFIX,
    KeySchema,
    RecordTable,
    SetAttribute,
    validate_record_item,
    validate_record_update,
)

pytestmark = pytest.mark.unit

TABLE = RecordTable(name="things", key=KeySchema(partition="pk"))


@pytest.mark.parametrize("item", [{"pk": "a"}, {"pk": "a", "_private": 1, "rs_token": "x", "value": None}])
def test_ordinary_attribute_names_are_accepted(item: dict[str, object]) -> None:
    validate_record_item(item)


def test_a_reserved_attribute_name_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="_rs_write_token"):
        validate_record_item({"pk": "a", f"{RESERVED_ATTRIBUTE_PREFIX}write_token": "forged"})


def test_an_update_may_not_set_a_reserved_attribute() -> None:
    with pytest.raises(ValueError, match="reserved"):
        validate_record_update(TABLE, {"pk": "a"}, [SetAttribute(f"{RESERVED_ATTRIBUTE_PREFIX}write_token", "x")], None)


def test_an_update_may_not_guard_a_reserved_attribute() -> None:
    with pytest.raises(ValueError, match="reserved"):
        validate_record_update(TABLE, {"pk": "a"}, [SetAttribute("value", 1)], {f"{RESERVED_ATTRIBUTE_PREFIX}write_token": "x"})
