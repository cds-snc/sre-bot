"""The postmortem slot rules: which candidate slot a meeting gets and why, as pure functions.

Inputs are built by hand: a policy, attendees, the calendars' answers keyed by
case-folded email (as ``CalendarAvailability`` returns them) and a list of
candidate slots, so each test states exactly who is busy when. Assertions read
the chosen slot and the named explanations: no required attendee may be busy, a
required attendee whose calendar is unknown is allowed but named, the optional
quorum is a percentage of the optional attendees counted (unknown counts as not
free), an optional attendee busy at every candidate is excluded from the count
and named, and a required attendee busy at every candidate stops the search.
"""

from datetime import UTC, datetime, time, timedelta

import pytest

from features.incident.core.api import AttendeeBusy, BusyInterval
from features.incident.postmortem.domain import (
    Attendee,
    Availability,
    NoSlotReason,
    Slot,
    SlotPolicy,
    attendee_list,
    attendee_overview,
    availability_at,
    find_slot,
)

pytestmark = pytest.mark.unit

T0 = datetime(2026, 12, 1, 18, 0, tzinfo=UTC)
SLOTS = tuple(Slot(start=T0 + timedelta(days=n), end=T0 + timedelta(days=n, minutes=30)) for n in range(3))


def _policy(quorum: int = 50) -> SlotPolicy:
    return SlotPolicy(
        time_zone="America/Toronto",
        window_start=time(13, 0),
        window_end=time(15, 0),
        weekdays=frozenset({1, 2, 3, 4, 5}),
        duration=timedelta(minutes=30),
        step=timedelta(minutes=30),
        search_days=60,
        optional_quorum_percent=quorum,
    )


def _required(name: str) -> Attendee:
    return Attendee(account_id=f"U0{name.upper()}", email=f"{name}@example.org", required=True)


def _optional(name: str) -> Attendee:
    return Attendee(account_id=f"U0{name.upper()}", email=f"{name}@example.org", required=False)


def _busy_at(*slots: Slot) -> tuple[BusyInterval, ...]:
    return tuple(BusyInterval(start=slot.start, end=slot.end) for slot in slots)


def _answers(**busy: tuple[BusyInterval, ...] | None) -> dict[str, AttendeeBusy]:
    return {f"{name}@example.org": AttendeeBusy(email=f"{name}@example.org", busy=value) for name, value in busy.items()}


def test_availability_is_busy_on_overlap_free_otherwise_and_unknown_without_an_answer() -> None:
    slot = SLOTS[0]
    touching = BusyInterval(start=slot.end, end=slot.end + timedelta(hours=1))
    overlapping = BusyInterval(start=slot.start - timedelta(minutes=10), end=slot.start + timedelta(minutes=1))

    assert availability_at(AttendeeBusy(email="a", busy=(touching,)), slot) is Availability.FREE
    assert availability_at(AttendeeBusy(email="a", busy=(overlapping,)), slot) is Availability.BUSY
    assert availability_at(AttendeeBusy(email="a", busy=None), slot) is Availability.UNKNOWN
    assert availability_at(None, slot) is Availability.UNKNOWN


def test_a_busy_required_attendee_blocks_the_slot_and_the_earliest_free_one_wins() -> None:
    search = find_slot(_policy(), (_required("ada"), _optional("bo")), _answers(ada=_busy_at(SLOTS[0]), bo=()), SLOTS)

    assert search.slot == SLOTS[1]
    assert search.reason is None


def test_a_required_attendee_whose_calendar_is_unknown_is_allowed_and_named() -> None:
    ada = _required("ada")

    search = find_slot(_policy(), (ada,), _answers(ada=None), SLOTS)

    assert search.slot == SLOTS[0]
    assert search.required_unknown == (ada,)


def test_a_required_attendee_without_an_email_is_unknown_never_free() -> None:
    ada = Attendee(account_id="U0ADA", email=None, required=True)

    search = find_slot(_policy(), (ada,), {}, SLOTS)

    assert search.slot == SLOTS[0]
    assert search.required_unknown == (ada,)


@pytest.mark.parametrize(
    ("quorum", "expected"),
    [(0, 0), (50, 0), (75, 1), (100, 2)],
    ids=["zero_never_blocks", "half", "three_quarters", "all"],
)
def test_the_optional_quorum_is_a_percentage_of_the_optional_attendees(quorum: int, expected: int) -> None:
    """Four optional attendees: two free at slot 0, three at slot 1, all four at slot 2."""
    answers = _answers(lead=(), a=_busy_at(SLOTS[0]), b=_busy_at(SLOTS[0], SLOTS[1]), c=(), d=())
    attendees = (_required("lead"), _optional("a"), _optional("b"), _optional("c"), _optional("d"))

    search = find_slot(_policy(quorum), attendees, answers, SLOTS)

    assert search.slot == SLOTS[expected]


def test_quorum_counts_an_unknown_optional_attendee_as_not_free() -> None:
    """Two optional attendees at 100 percent: one unknown, so no slot ever has both free."""
    attendees = (_required("lead"), _optional("a"), _optional("b"))

    search = find_slot(_policy(100), attendees, _answers(lead=(), a=(), b=None), SLOTS)

    assert search.slot is None
    assert search.reason is NoSlotReason.QUORUM_NEVER_MET


def test_an_optional_attendee_busy_at_every_candidate_is_excluded_from_the_count_and_named() -> None:
    away = _optional("away")
    attendees = (_required("lead"), away, _optional("bo"))

    search = find_slot(_policy(100), attendees, _answers(lead=(), away=_busy_at(*SLOTS), bo=()), SLOTS)

    assert search.slot == SLOTS[0]
    assert search.excluded_optional == (away,)


def test_the_chosen_slot_names_optional_attendees_busy_or_unknown_at_it() -> None:
    busy, unknown = _optional("busy"), _optional("unknown")
    attendees = (_required("lead"), busy, unknown, _optional("c"), _optional("d"))

    search = find_slot(_policy(50), attendees, _answers(lead=(), busy=_busy_at(SLOTS[0]), unknown=None, c=(), d=()), SLOTS)

    assert search.slot == SLOTS[0]
    assert search.optional_busy == (busy,)
    assert search.optional_unknown == (unknown,)


def test_no_optional_attendee_means_the_quorum_holds() -> None:
    search = find_slot(_policy(100), (_required("lead"),), _answers(lead=()), SLOTS)

    assert search.slot == SLOTS[0]


def test_a_required_attendee_busy_at_every_candidate_stops_the_search_naming_them() -> None:
    away = _required("away")

    search = find_slot(_policy(), (away, _required("lead")), _answers(away=_busy_at(*SLOTS), lead=()), SLOTS)

    assert search.slot is None
    assert search.reason is NoSlotReason.REQUIRED_ALWAYS_BUSY
    assert search.blocking_required == (away,)


def test_required_attendees_never_free_together_is_its_own_reason() -> None:
    attendees = (_required("a"), _required("b"))

    search = find_slot(_policy(), attendees, _answers(a=_busy_at(SLOTS[0], SLOTS[2]), b=_busy_at(SLOTS[1])), SLOTS)

    assert search.slot is None
    assert search.reason is NoSlotReason.REQUIRED_NEVER_FREE_TOGETHER


def test_no_candidate_and_no_attendee_are_reasons_not_errors() -> None:
    assert find_slot(_policy(), (_required("a"),), _answers(a=()), ()).reason is NoSlotReason.NO_CANDIDATE
    assert find_slot(_policy(), (), {}, SLOTS).reason is NoSlotReason.NO_ATTENDEES


def test_attendee_list_keeps_required_first_and_an_account_in_both_sets_counts_as_required() -> None:
    attendees = attendee_list(
        required=("U0A", "U0B"),
        optional=("U0B", "U0C", "U0C"),
        emails={"U0A": "a@example.org", "U0B": "b@example.org", "U0C": None},
    )

    assert attendees == (
        Attendee(account_id="U0A", email="a@example.org", required=True),
        Attendee(account_id="U0B", email="b@example.org", required=True),
        Attendee(account_id="U0C", email=None, required=False),
    )


def test_the_overview_names_who_is_busy_at_every_candidate_and_whose_calendar_is_unknown() -> None:
    """The modal's warning: the legacy heuristic flagged only one busy block near both window edges."""
    away, unknown, free = _optional("away"), _required("unknown"), _optional("free")
    answers = _answers(away=_busy_at(*SLOTS), unknown=None, free=_busy_at(SLOTS[0]))

    overview = attendee_overview((away, unknown, free), answers, SLOTS)

    assert overview.always_busy == (away,)
    assert overview.unknown == (unknown,)
