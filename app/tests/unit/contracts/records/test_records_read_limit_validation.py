"""Unit tests for the whole-table read cap check in the records contract.

``validate_read_limit`` is the shared check both stores run before reading:
a cap below one is a caller programming error and raises ``ValueError``,
like ``RecordQuery.limit``; the error code constant is the stable value
callers match on when the table holds more than the cap.
"""

import pytest

from contracts.records import READ_LIMIT_EXCEEDED, validate_read_limit

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("max_items", [0, -1])
def test_a_cap_below_one_is_rejected(max_items: int) -> None:
    with pytest.raises(ValueError, match="max_items must be at least 1"):
        validate_read_limit(max_items)


def test_a_cap_of_one_is_accepted() -> None:
    validate_read_limit(1)


def test_the_over_cap_error_code_is_stable() -> None:
    assert READ_LIMIT_EXCEEDED == "RECORD_READ_LIMIT_EXCEEDED"
