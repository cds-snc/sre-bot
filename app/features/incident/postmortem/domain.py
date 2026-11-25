"""Postmortem domain: the meeting search rules as pure functions, and the legacy availability helpers.

The availability model (TASK-145.10.3): each attendee is free, busy or unknown at a
candidate slot (a calendar that could not be read, or an account without an email,
is unknown and never free). A slot qualifies when no required attendee is busy (a
required unknown is allowed and named) and the optional quorum holds; the earliest
qualifying slot wins. Candidate slots are built per local date in the meeting's
zone, so the UTC hour follows daylight saving time, over the weekdays of the policy
and skipping the holidays of every year the search spans. Nothing here reads a
clock or does I/O: ``now``, the holidays and the calendars' answers are passed in.

The legacy helpers below (``find_first_available_slot``, ``get_utc_hour``,
``identify_unavailable_users``) were moved verbatim from
features/incident/scheduling/availability.py (TASK-145.10.1) and serve the legacy
flow until the cutover (TASK-145.10.4) deletes them.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

import pytz

from features.incident.core.api import AttendeeBusy
from features.incident.postmortem.adapters.public_holidays import get_federal_holidays


class Availability(StrEnum):
    """An attendee at a candidate slot."""

    FREE = "free"
    BUSY = "busy"
    UNKNOWN = "unknown"


class HolidayLookupFailure(StrEnum):
    """What a schedule does when the holiday list cannot be read: the [incident_postmortem] setting."""

    PROCEED = "proceed"
    REFUSE = "refuse"


class NoSlotReason(StrEnum):
    """Why a search found no slot."""

    NO_ATTENDEES = "no_attendees"
    NO_CANDIDATE = "no_candidate"
    REQUIRED_ALWAYS_BUSY = "required_always_busy"
    REQUIRED_NEVER_FREE_TOGETHER = "required_never_free_together"
    QUORUM_NEVER_MET = "quorum_never_met"
    HOLIDAYS_UNAVAILABLE = "holidays_unavailable"


@dataclass(frozen=True)
class SlotPolicy:
    """The meeting search policy, built from the [incident_postmortem] settings.

    Attributes:
        time_zone: IANA zone the window and the meeting are in.
        window_start: Local time the first slot of a day may start.
        window_end: Local time the last slot of a day must end by.
        weekdays: ISO weekdays (1 Monday to 7 Sunday) a meeting may be on.
        duration: The meeting's length.
        step: Time between two candidate starts on a day.
        search_days: How many days, from the first date, the search covers.
        optional_quorum_percent: The share of counted optional attendees that must be free.
    """

    time_zone: str
    window_start: time
    window_end: time
    weekdays: frozenset[int]
    duration: timedelta
    step: timedelta
    search_days: int
    optional_quorum_percent: int

    @property
    def zone(self) -> ZoneInfo:
        """The policy's zone."""
        return ZoneInfo(self.time_zone)


@dataclass(frozen=True)
class Slot:
    """A candidate meeting time: aware, ending after it starts."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.utcoffset() is None or self.end.utcoffset() is None:
            raise ValueError("a slot's start and end must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("a slot must end after it starts")


@dataclass(frozen=True)
class Attendee:
    """A person asked to the meeting: an account, its email (``None`` when it has none), required or optional."""

    account_id: str
    email: str | None
    required: bool


@dataclass(frozen=True)
class SlotSearch:
    """A search's outcome: the slot (or ``None`` with a reason) and the people to name.

    Attributes:
        slot: The earliest qualifying slot, ``None`` when none qualifies.
        reason: Why no slot qualifies; ``None`` with a slot.
        required_unknown: Required attendees whose calendar is unknown at the slot.
        optional_busy: Counted optional attendees busy at the slot.
        optional_unknown: Counted optional attendees whose calendar is unknown at the slot.
        excluded_optional: Optional attendees busy at every candidate, left out of the quorum.
        blocking_required: Required attendees busy at every candidate (the search stops).
    """

    slot: Slot | None
    reason: NoSlotReason | None = None
    required_unknown: tuple[Attendee, ...] = ()
    optional_busy: tuple[Attendee, ...] = ()
    optional_unknown: tuple[Attendee, ...] = ()
    excluded_optional: tuple[Attendee, ...] = ()
    blocking_required: tuple[Attendee, ...] = ()


@dataclass(frozen=True)
class AttendeeOverview:
    """Who cannot be counted on over the whole search: busy at every candidate, or unknown."""

    always_busy: tuple[Attendee, ...]
    unknown: tuple[Attendee, ...]


@dataclass(frozen=True)
class LocalTime:
    """A moment's parts in the policy's zone, for catalogue wording: ISO weekday, date, 24-hour clock and zone abbreviation."""

    weekday: int
    day: int
    month: int
    year: int
    clock: str
    zone: str


def attendee_list(*, required: Sequence[str], optional: Sequence[str], emails: Mapping[str, str | None]) -> tuple[Attendee, ...]:
    """The attendees, required first, each account once; an account in both sets is required."""
    required_ids = tuple(dict.fromkeys(required))
    optional_ids = tuple(account for account in dict.fromkeys(optional) if account not in required_ids)
    return tuple(Attendee(account, emails.get(account), True) for account in required_ids) + tuple(
        Attendee(account, emails.get(account), False) for account in optional_ids
    )


def search_start_date(policy: SlotPolicy, now: datetime, start_after_days: int) -> date:
    """The first date of the search: today in the policy's zone plus ``start_after_days``."""
    return now.astimezone(policy.zone).date() + timedelta(days=start_after_days)


def search_dates(policy: SlotPolicy, first: date) -> tuple[date, ...]:
    """Every date the search covers, from ``first``."""
    return tuple(first + timedelta(days=offset) for offset in range(policy.search_days))


def search_years(policy: SlotPolicy, first: date) -> frozenset[int]:
    """Every year the search spans: the holiday lookup asks for each one."""
    return frozenset(day.year for day in search_dates(policy, first))


def candidate_slots(policy: SlotPolicy, first: date, holidays: frozenset[date], *, now: datetime) -> tuple[Slot, ...]:
    """The candidate slots in time order: the policy's weekdays, not holidays, inside the local window, after ``now``.

    Each date's window is its local start and end time in the policy's zone, so the UTC
    hour follows daylight saving time per date.
    """
    zone = policy.zone
    slots: list[Slot] = []
    for day in search_dates(policy, first):
        if day.isoweekday() not in policy.weekdays or day in holidays:
            continue
        start = datetime.combine(day, policy.window_start, tzinfo=zone)
        window_end = datetime.combine(day, policy.window_end, tzinfo=zone)
        while start + policy.duration <= window_end:
            if start > now:
                slots.append(Slot(start=start, end=start + policy.duration))
            start += policy.step
    return tuple(slots)


def availability_at(answer: AttendeeBusy | None, slot: Slot) -> Availability:
    """Free, busy or unknown at ``slot``: no answer, or a calendar that could not be read, is unknown."""
    if answer is None or answer.busy is None:
        return Availability.UNKNOWN
    if any(interval.start < slot.end and interval.end > slot.start for interval in answer.busy):
        return Availability.BUSY
    return Availability.FREE


def _answer(attendee: Attendee, busy: Mapping[str, AttendeeBusy]) -> AttendeeBusy | None:
    return busy.get(attendee.email.strip().casefold()) if attendee.email else None


def _always_busy(attendee: Attendee, busy: Mapping[str, AttendeeBusy], candidates: Sequence[Slot]) -> bool:
    answer = _answer(attendee, busy)
    return all(availability_at(answer, slot) is Availability.BUSY for slot in candidates)


def _quorum_holds(free: int, counted: int, percent: int) -> bool:
    return counted == 0 or free * 100 >= percent * counted


def find_slot(
    policy: SlotPolicy, attendees: Sequence[Attendee], busy: Mapping[str, AttendeeBusy], candidates: Sequence[Slot]
) -> SlotSearch:
    """The earliest candidate where no required attendee is busy and the optional quorum holds.

    ``busy`` is keyed by stripped, case-folded email, as ``CalendarAvailability`` answers.
    An optional attendee busy at every candidate is left out of the count and named; a
    required one stops the search.
    """
    if not attendees:
        return SlotSearch(slot=None, reason=NoSlotReason.NO_ATTENDEES)
    if not candidates:
        return SlotSearch(slot=None, reason=NoSlotReason.NO_CANDIDATE)
    required = tuple(attendee for attendee in attendees if attendee.required)
    blocking = tuple(attendee for attendee in required if _always_busy(attendee, busy, candidates))
    if blocking:
        return SlotSearch(slot=None, reason=NoSlotReason.REQUIRED_ALWAYS_BUSY, blocking_required=blocking)
    optional = tuple(attendee for attendee in attendees if not attendee.required)
    excluded = tuple(attendee for attendee in optional if _always_busy(attendee, busy, candidates))
    counted = tuple(attendee for attendee in optional if attendee not in excluded)
    required_free_somewhere = False
    for slot in candidates:
        if any(availability_at(_answer(attendee, busy), slot) is Availability.BUSY for attendee in required):
            continue
        required_free_somewhere = True
        at_slot = {attendee: availability_at(_answer(attendee, busy), slot) for attendee in counted}
        free = sum(1 for state in at_slot.values() if state is Availability.FREE)
        if not _quorum_holds(free, len(counted), policy.optional_quorum_percent):
            continue
        return SlotSearch(
            slot=slot,
            required_unknown=tuple(
                attendee for attendee in required if availability_at(_answer(attendee, busy), slot) is Availability.UNKNOWN
            ),
            optional_busy=tuple(attendee for attendee, state in at_slot.items() if state is Availability.BUSY),
            optional_unknown=tuple(attendee for attendee, state in at_slot.items() if state is Availability.UNKNOWN),
            excluded_optional=excluded,
        )
    reason = NoSlotReason.QUORUM_NEVER_MET if required_free_somewhere else NoSlotReason.REQUIRED_NEVER_FREE_TOGETHER
    return SlotSearch(slot=None, reason=reason, excluded_optional=excluded)


def attendee_overview(
    attendees: Sequence[Attendee], busy: Mapping[str, AttendeeBusy], candidates: Sequence[Slot]
) -> AttendeeOverview:
    """Who is busy at every candidate, and whose calendar is unknown: the schedule view's warning."""
    unknown = tuple(attendee for attendee in attendees if (answer := _answer(attendee, busy)) is None or answer.busy is None)
    always_busy = tuple(
        attendee for attendee in attendees if attendee not in unknown and candidates and _always_busy(attendee, busy, candidates)
    )
    return AttendeeOverview(always_busy=always_busy, unknown=unknown)


def local_time(moment: datetime, policy: SlotPolicy) -> LocalTime:
    """``moment`` in the policy's zone, as parts a catalogue sentence fills in; the abbreviation is that date's own."""
    local = moment.astimezone(policy.zone)
    return LocalTime(
        weekday=local.isoweekday(),
        day=local.day,
        month=local.month,
        year=local.year,
        clock=local.strftime("%H:%M"),
        zone=local.tzname() or policy.time_zone,
    )


# Function to use the freebusy response to find the first available spot in the next 60 days. We look for a 30 minute windows, 3
# days in the future, ignoring weekends
def find_first_available_slot(freebusy_response, days_in_future, duration_minutes=30, search_days_limit=60):
    # EST timezone
    est = pytz.timezone("US/Eastern")

    starting_hour = get_utc_hour(13, 0, "US/Eastern")
    ending_hour = get_utc_hour(15, 0, "US/Eastern")

    # Combine all busy times into a single list and sort them
    busy_times = []
    for calendar in freebusy_response["calendars"].values():
        for busy_period in calendar["busy"]:
            # convert from iso 8601 standard to datetime
            start = datetime.fromisoformat(busy_period["start"][:-1])
            end = datetime.fromisoformat(busy_period["end"][:-1])
            busy_times.append((start, end))
    busy_times.sort(key=lambda x: x[0])

    # get the list of Canandian federal holidays
    federal_holidays = get_federal_holidays()

    for day_offset in range(days_in_future, days_in_future + search_days_limit):
        # Calculate the start and end times of the search window for the current day
        search_date = datetime.utcnow() + timedelta(days=day_offset)

        # Check if the day is Saturday (5) or Sunday (6) and skip it
        if search_date.weekday() in [5, 6]:
            continue

        search_start = search_date.replace(hour=starting_hour, minute=0, second=0, microsecond=0)  # 1 PM EST, times are in UTC
        search_end = search_date.replace(hour=ending_hour, minute=0, second=0, microsecond=0)  # 3 PM EST, times are in UTC

        # if the day is a federal holiday, skip it
        if search_date.date().strftime("%Y-%m-%d") in federal_holidays:
            continue

        # Attempt to find an available slot within this day's search window
        for current_time in (search_start + timedelta(minutes=i) for i in range(0, 121, duration_minutes)):
            slot_end = current_time + timedelta(minutes=duration_minutes)
            if all(slot_end <= start or current_time >= end for start, end in busy_times) and slot_end <= search_end:
                # return the time and convert them to EST timezone
                return current_time.astimezone(est), slot_end.astimezone(est)

    return None, None  # No available slot found after searching the limit


def get_utc_hour(hour, minute, tz_name, date=None):
    """
    Converts a specific time in a given time zone to UTC and returns the hour.

    Args:
        hour (int): The hour of the time in 24-hour format.
        minute (int): The minute of the time.
        tz_name (str): The name of the time zone (e.g., "US/Eastern").

    Returns:
        str: The corresponding UTC hour.
    """
    # Define the local timezone
    local_tz = pytz.timezone(tz_name)

    # If we are not passing the date, then initialize it to the current date:w
    if date is None:
        date = datetime.utcnow()

    # Create a datetime object for the given time in the local timezone
    local_time = local_tz.localize(datetime(date.year, date.month, date.day, hour, minute))

    # Convert to UTC
    utc_time = local_time.astimezone(pytz.utc)

    return utc_time.hour


def identify_unavailable_users(freebusy_response, time_min: str, time_max: str):
    """
    Identifies users who appear to have calendar configuration issues
    or are completely unavailable during the entire specified time range.

    Args:
        freebusy_response (dict): Response from the freebusy API
        time_min (str): ISO format string for start time with 'Z' suffix
        time_max (str): ISO format string for end time with 'Z' suffix

    Returns:
        list: List of emails of users with potential calendar issues
    """
    unavailable_user_emails = []

    # Convert time_min and time_max to datetime objects
    start_dt = datetime.fromisoformat(time_min[:-1]).replace(tzinfo=UTC)
    end_dt = datetime.fromisoformat(time_max[:-1]).replace(tzinfo=UTC)

    # Check each calendar
    for email, calendar_data in freebusy_response["calendars"].items():
        # Skip if there are errors or no busy data
        if "errors" in calendar_data or "busy" not in calendar_data:
            continue

        busy_periods = calendar_data["busy"]

        if len(busy_periods) == 1:
            busy_start = datetime.fromisoformat(busy_periods[0]["start"][:-1]).replace(tzinfo=UTC)
            busy_end = datetime.fromisoformat(busy_periods[0]["end"][:-1]).replace(tzinfo=UTC)

            # Calculate how close the busy period is to the search period boundaries
            start_diff = abs((busy_start - start_dt).total_seconds())
            end_diff = abs((busy_end - end_dt).total_seconds())

            # If within 1 hour of both boundaries, this is likely a configuration issue
            if start_diff < 3600 and end_diff < 3600:
                unavailable_user_emails.append(email)
                continue

    return unavailable_user_emails
