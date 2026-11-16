"""Unit tests for the weekly rotation assignment logic of the on-call domain.

Pure functions over frozen values, so there is nothing to stub. Assertions are on the member
chosen and the shift windows produced at fixed instants, never on the wall clock.
"""

from datetime import UTC, datetime, timedelta

import pytest

from capabilities.oncall.domain import OnCallPerson, Rotation, shift_windows, whos_on

pytestmark = pytest.mark.unit

START = datetime(2026, 1, 5, 9, tzinfo=UTC)


def _rotation(members: int = 3, weeks_per_shift: int = 1) -> Rotation:
    people = tuple(OnCallPerson(email=f"m{index}@example.org", account=None) for index in range(members))
    return Rotation(name="r", members=people, weeks_per_shift=weeks_per_shift, start=START)


def _email(person: OnCallPerson) -> str | None:
    return person.email


def test_first_member_is_on_call_at_the_start() -> None:
    assert _email(whos_on(_rotation(), START)) == "m0@example.org"


def test_second_member_takes_over_after_one_week() -> None:
    assert _email(whos_on(_rotation(), START + timedelta(weeks=1, hours=1))) == "m1@example.org"


def test_member_changes_exactly_at_the_shift_boundary() -> None:
    boundary = START + timedelta(weeks=1)

    assert _email(whos_on(_rotation(), boundary - timedelta(seconds=1))) == "m0@example.org"
    assert _email(whos_on(_rotation(), boundary)) == "m1@example.org"


def test_shift_of_two_weeks_keeps_the_member_for_both_weeks() -> None:
    rotation = _rotation(weeks_per_shift=2)

    assert _email(whos_on(rotation, START + timedelta(weeks=1, days=6))) == "m0@example.org"
    assert _email(whos_on(rotation, START + timedelta(weeks=2))) == "m1@example.org"


def test_order_wraps_around_after_the_last_member() -> None:
    assert _email(whos_on(_rotation(members=3), START + timedelta(weeks=3))) == "m0@example.org"


def test_single_member_is_always_on_call() -> None:
    rotation = _rotation(members=1)

    assert _email(whos_on(rotation, START + timedelta(weeks=17))) == "m0@example.org"


def test_a_start_in_the_future_counts_back_from_the_start_with_wrap_around() -> None:
    assert _email(whos_on(_rotation(members=3), START - timedelta(days=1))) == "m2@example.org"


def test_shift_windows_begin_with_the_active_shift_and_stop_at_the_horizon() -> None:
    at = START + timedelta(weeks=1, days=2)

    shifts = shift_windows(_rotation(), at, horizon_weeks=2)

    assert [(_email(shift.person), shift.start) for shift in shifts] == [
        ("m1@example.org", START + timedelta(weeks=1)),
        ("m2@example.org", START + timedelta(weeks=2)),
        ("m0@example.org", START + timedelta(weeks=3)),
    ]
    assert shifts[0].end == START + timedelta(weeks=2)
