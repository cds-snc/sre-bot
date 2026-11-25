"""Incident postmortem settings: the [incident_postmortem] table of the configuration files.

The calendar id is a non-public value (decisions/configuration.md): declared empty in
base.toml, set only from the environment as INCIDENT_POSTMORTEM__CALENDAR_ID. Every
meeting search policy, tuning and bound value is a typed field whose default mirrors
base.toml; an out-of-range value fails the slice at boot, naming the field.
"""

from datetime import time, timedelta
from functools import lru_cache
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only
from features.incident.postmortem.domain import HolidayLookupFailure, SlotPolicy


class IncidentPostmortemSettings(ConfigurationSlice):
    """Where the retro meeting is booked, and how its time is chosen.

    Environment only (non-public values):
        INCIDENT_POSTMORTEM__CALENDAR_ID.
    """

    model_config = SettingsConfigDict(toml_table_header=("incident_postmortem",), env_prefix="INCIDENT_POSTMORTEM__")

    calendar_id: str = env_only("Google Calendar id the retro meeting is booked on.", "codespaces", default="")
    time_zone: str = Field(default="America/Toronto", description="IANA zone of the meeting window and the meeting.")
    window_start: time = Field(default=time(13, 0), description="Local time the first meeting of a day may start.")
    window_end: time = Field(default=time(15, 0), description="Local time the last meeting of a day must end by.")
    weekdays: tuple[int, ...] = Field(
        default=(1, 2, 3, 4, 5), description="ISO weekdays (1 Monday to 7 Sunday) a meeting may be on."
    )
    duration_minutes: int = Field(default=30, description="The meeting's length; it fits inside the window.")
    slot_step_minutes: int = Field(default=30, gt=0, description="Minutes between two candidate starts on a day.")
    search_days: int = Field(default=60, ge=1, le=120, description="Days the search covers from its first date.")
    default_start_offset_days: int = Field(
        default=1, ge=0, description="Days after today the search starts unless the person picks another number."
    )
    max_start_offset_days: int = Field(default=60, ge=1, description="The most days after today a person may start the search.")
    optional_quorum_percent: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Share of optional attendees that must be free; 0 never blocks, 100 needs every one counted.",
    )
    holiday_lookup_failure: HolidayLookupFailure = Field(
        default=HolidayLookupFailure.PROCEED,
        description="When the holiday list cannot be read: proceed without holidays (and say so) or refuse to book.",
    )

    @field_validator("time_zone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"{value!r} is not an IANA time zone") from exc
        return value

    @field_validator("weekdays")
    @classmethod
    def _iso_weekdays_once_each(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value:
            raise ValueError("needs at least one weekday")
        if any(day < 1 or day > 7 for day in value):
            raise ValueError("weekdays are ISO numbers, 1 Monday to 7 Sunday")
        if len(set(value)) != len(value):
            raise ValueError("lists a weekday more than once")
        return value

    @model_validator(mode="after")
    def _window_fits(self) -> Self:
        window = timedelta(hours=self.window_end.hour, minutes=self.window_end.minute) - timedelta(
            hours=self.window_start.hour, minutes=self.window_start.minute
        )
        if window <= timedelta(0):
            raise ValueError("window_end must be after window_start")
        if self.duration_minutes <= 0 or timedelta(minutes=self.duration_minutes) > window:
            raise ValueError("duration_minutes must be positive and fit between window_start and window_end")
        if self.default_start_offset_days > self.max_start_offset_days:
            raise ValueError("default_start_offset_days must not exceed max_start_offset_days")
        return self

    def slot_policy(self) -> SlotPolicy:
        """The search policy these settings describe."""
        return SlotPolicy(
            time_zone=self.time_zone,
            window_start=self.window_start,
            window_end=self.window_end,
            weekdays=frozenset(self.weekdays),
            duration=timedelta(minutes=self.duration_minutes),
            step=timedelta(minutes=self.slot_step_minutes),
            search_days=self.search_days,
            optional_quorum_percent=self.optional_quorum_percent,
        )


@lru_cache(maxsize=1)
def get_incident_postmortem_settings() -> IncidentPostmortemSettings:
    """Return the process-wide [incident_postmortem] slice."""
    return IncidentPostmortemSettings()
