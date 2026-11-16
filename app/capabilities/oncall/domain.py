"""On-call domain types and the weekly rotation assignment logic.

Frozen dataclasses only: the vocabulary of ``api.py``, free of any vendor, platform or
feature. ``whos_on`` and ``shift_windows`` implement the self-managed weekly rotation: the
member at ``start`` takes the first shift, each shift lasts ``weeks_per_shift`` weeks and
the order wraps around.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

OPSGENIE = "opsgenie"
ROTATIONS = "rotations"


@dataclass(frozen=True)
class ScheduleReference:
    """A schedule in one source system: ``system`` selects the source, ``id`` is the source's key."""

    system: str
    id: str


@dataclass(frozen=True)
class Account:
    """A person's account on one platform, in one tenant when the platform has tenants."""

    platform: str
    tenant: str | None
    account_id: str


@dataclass(frozen=True)
class OnCallPerson:
    """A person on call, by email, by platform account, or both."""

    email: str | None
    account: Account | None

    def __post_init__(self) -> None:
        if self.email is None and self.account is None:
            raise ValueError("an on-call person needs an email or an account")


@dataclass(frozen=True)
class Shift:
    """One person on call from ``start`` (inclusive) to ``end`` (exclusive)."""

    person: OnCallPerson
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Rotation:
    """A weekly rotation: ``members`` take turns for ``weeks_per_shift`` weeks from ``start``."""

    name: str
    members: tuple[OnCallPerson, ...]
    weeks_per_shift: int
    start: datetime


@dataclass(frozen=True)
class Schedule:
    """A schedule with its rotations and the shifts from the active one through the horizon."""

    reference: ScheduleReference
    name: str
    rotations: tuple[Rotation, ...]
    shifts: tuple[Shift, ...]


def whos_on(rotation: Rotation, at: datetime) -> OnCallPerson:
    """Return the member on call at ``at``; a time before ``start`` counts back from it, wrapping."""
    period = timedelta(weeks=rotation.weeks_per_shift)
    return rotation.members[((at - rotation.start) // period) % len(rotation.members)]


def shift_windows(rotation: Rotation, at: datetime, horizon_weeks: int) -> tuple[Shift, ...]:
    """Return the shift active at ``at`` and every shift starting before ``at`` plus ``horizon_weeks``."""
    period = timedelta(weeks=rotation.weeks_per_shift)
    start = rotation.start + ((at - rotation.start) // period) * period
    end = at + timedelta(weeks=horizon_weeks)
    shifts: list[Shift] = []
    while start < end:
        shifts.append(Shift(person=whos_on(rotation, start), start=start, end=start + period))
        start += period
    return tuple(shifts)
