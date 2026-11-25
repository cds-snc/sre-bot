"""The postmortem candidate slots: per-date local windows, weekdays, holidays across a year end (NC7).

Pure functions with fixed dates and a fixed ``now``; no clock is read. The
window is local time in the policy's zone combined with each date, so the UTC
hour moves with daylight saving time (the legacy converted 13:00 US/Eastern to
a UTC hour once, for today). The holiday years are every year the search spans,
so a search crossing 31 December skips the next year's observed holidays too
(the legacy asked for the current year only). The local-time parts carry each
date's own zone abbreviation (the legacy always printed EDT).
"""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from features.incident.postmortem.domain import (
    LocalTime,
    Slot,
    SlotPolicy,
    candidate_slots,
    local_time,
    search_start_date,
    search_years,
)

pytestmark = pytest.mark.unit

LONG_AGO = datetime(2020, 1, 1, tzinfo=UTC)


def _policy(**overrides: object) -> SlotPolicy:
    values: dict[str, object] = {
        "time_zone": "America/Toronto",
        "window_start": time(13, 0),
        "window_end": time(15, 0),
        "weekdays": frozenset({1, 2, 3, 4, 5}),
        "duration": timedelta(minutes=30),
        "step": timedelta(minutes=30),
        "search_days": 1,
        "optional_quorum_percent": 50,
    }
    values.update(overrides)
    return SlotPolicy(**values)  # type: ignore[arg-type]


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    ("day", "utc_hour"),
    [
        (date(2026, 10, 30), 17),  # Friday, EDT (UTC-4)
        (date(2026, 11, 2), 18),  # Monday after DST ended on 1 November, EST (UTC-5)
        (date(2027, 3, 12), 18),  # Friday before DST starts on 14 March, EST
        (date(2027, 3, 15), 17),  # Monday after, EDT
    ],
)
def test_the_window_is_local_time_on_each_date_so_the_utc_hour_follows_dst(day: date, utc_hour: int) -> None:
    slots = candidate_slots(_policy(), day, frozenset(), now=LONG_AGO)

    assert [slot.start.astimezone(UTC) for slot in slots] == [
        _utc(day.year, day.month, day.day, utc_hour),
        _utc(day.year, day.month, day.day, utc_hour, 30),
        _utc(day.year, day.month, day.day, utc_hour + 1),
        _utc(day.year, day.month, day.day, utc_hour + 1, 30),
    ]
    assert all(slot.end - slot.start == timedelta(minutes=30) for slot in slots)


def test_slots_step_by_the_step_and_end_by_the_window_end() -> None:
    """A 50-minute meeting stepping by 20 minutes: 13:00, 13:20, 13:40 and 14:00 fit before 15:00, 14:20 does not."""
    policy = _policy(duration=timedelta(minutes=50), step=timedelta(minutes=20))

    slots = candidate_slots(policy, date(2026, 12, 1), frozenset(), now=LONG_AGO)

    assert [slot.start.astimezone(UTC).strftime("%H:%M") for slot in slots] == ["18:00", "18:20", "18:40", "19:00"]
    assert slots[-1].end.astimezone(UTC) == _utc(2026, 12, 1, 19, 50)


def test_a_search_across_the_year_end_skips_weekends_and_both_years_holidays() -> None:
    policy = _policy(search_days=30, step=timedelta(hours=2), duration=timedelta(minutes=30))
    holidays = frozenset({date(2026, 12, 25), date(2026, 12, 28), date(2027, 1, 1)})
    first = date(2026, 12, 20)

    days = [slot.start.date() for slot in candidate_slots(policy, first, holidays, now=LONG_AGO)]

    assert search_years(policy, first) == frozenset({2026, 2027})
    assert days[:6] == [
        date(2026, 12, 21),
        date(2026, 12, 22),
        date(2026, 12, 23),
        date(2026, 12, 24),
        date(2026, 12, 29),
        date(2026, 12, 30),
    ]
    assert date(2027, 1, 1) not in days
    assert days[-1] == date(2027, 1, 18)


def test_weekdays_come_from_the_policy() -> None:
    policy = _policy(search_days=7, weekdays=frozenset({2, 4}), step=timedelta(hours=2))

    days = [slot.start.date() for slot in candidate_slots(policy, date(2026, 11, 30), frozenset(), now=LONG_AGO)]

    assert days == [date(2026, 12, 1), date(2026, 12, 3)]


def test_slots_that_start_before_now_are_skipped() -> None:
    now = _utc(2026, 12, 1, 18, 45)

    slots = candidate_slots(_policy(), date(2026, 12, 1), frozenset(), now=now)

    assert [slot.start.astimezone(UTC) for slot in slots] == [_utc(2026, 12, 1, 19), _utc(2026, 12, 1, 19, 30)]


def test_the_search_starts_on_the_local_date_of_now_plus_the_offset() -> None:
    """At 02:00Z on 2 December it is still 1 December in Toronto."""
    now = _utc(2026, 12, 2, 2)

    assert search_start_date(_policy(), now, 0) == date(2026, 12, 1)
    assert search_start_date(_policy(), now, 3) == date(2026, 12, 4)


def test_the_years_of_a_search_inside_one_year_are_that_year() -> None:
    assert search_years(_policy(search_days=60), date(2026, 3, 1)) == frozenset({2026})


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (_utc(2026, 10, 30, 17), LocalTime(weekday=5, day=30, month=10, year=2026, clock="13:00", zone="EDT")),
        (_utc(2026, 11, 2, 18, 30), LocalTime(weekday=1, day=2, month=11, year=2026, clock="13:30", zone="EST")),
    ],
)
def test_local_time_parts_carry_each_dates_zone_abbreviation(moment: datetime, expected: LocalTime) -> None:
    assert local_time(moment, _policy()) == expected


def test_a_slot_is_aware_and_ends_after_it_starts() -> None:
    with pytest.raises(ValueError, match="aware"):
        Slot(start=datetime(2026, 12, 1, 13), end=datetime(2026, 12, 1, 14))  # noqa: DTZ001 -- the naive value under test
    with pytest.raises(ValueError, match="after"):
        Slot(start=_utc(2026, 12, 1, 18), end=_utc(2026, 12, 1, 18))
