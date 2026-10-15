"""Behavior tests for format_stored_time, the one writer of stored incident times.

Stored times are UTC instants with an explicit +00:00 offset at a fixed width,
so string order is time order in the open index sort key and the host timezone
never leaks in. The round trip goes through the end-state parser, the reader
of the same attributes.
"""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from features.incident.core.adapters.incident_items import format_stored_time, parse_incident_item

pytestmark = pytest.mark.unit

STORED_WIDTH = len("2026-10-15T14:00:00.000000+00:00")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2026, 10, 15, 14, 0, tzinfo=UTC), "2026-10-15T14:00:00.000000+00:00"),
        (datetime(2026, 10, 15, 14, 0, 5, 123456, tzinfo=UTC), "2026-10-15T14:00:05.123456+00:00"),
        # Newfoundland daylight time is UTC-02:30; the stored form is always UTC.
        (datetime(2026, 10, 15, 11, 30, tzinfo=timezone(timedelta(hours=-2, minutes=-30))), "2026-10-15T14:00:00.000000+00:00"),
        (datetime(2026, 10, 15, 7, 0, tzinfo=timezone(timedelta(hours=-7))), "2026-10-15T14:00:00.000000+00:00"),
    ],
)
def test_a_time_is_stored_as_fixed_width_utc_with_its_offset(value: datetime, expected: str) -> None:
    stored = format_stored_time(value)

    assert stored == expected
    assert len(stored) == STORED_WIDTH
    assert stored.endswith("+00:00")


def test_stored_times_sort_as_text_in_time_order() -> None:
    """Fixed width with microseconds always written: a whole second must not sort after its fractions."""
    earlier = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
    later = earlier + timedelta(microseconds=1)

    assert format_stored_time(earlier) < format_stored_time(later)


def test_a_naive_time_is_refused() -> None:
    """A time without an offset is a programming error: storing it would assume the host timezone."""
    with pytest.raises(ValueError, match="timezone-aware"):
        format_stored_time(datetime(2026, 10, 15, 14, 0))  # noqa: DTZ001


def test_a_stored_time_reads_back_as_the_same_instant() -> None:
    declared_at = datetime(2026, 10, 15, 9, 15, 30, 250000, tzinfo=timezone(timedelta(hours=-4)))
    item = {
        "id": "inc-1",
        "record_version": Decimal(1),
        "title": "Notify emails delayed",
        "status": "Open",
        "declared_by": "U0DECLARER",
        "declared_at": format_stored_time(declared_at),
        "security_incident": False,
    }

    result = parse_incident_item(item)

    assert result.data is not None
    assert result.data.declared_at == declared_at
    assert result.data.declared_at.utcoffset() == timedelta(0)
