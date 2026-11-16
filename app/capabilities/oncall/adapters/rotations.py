"""Self-managed rotations source: weekly rotations read from one JSON file each.

``RotationFile`` is the untrusted-file boundary (the keys of the existing rotation files,
``slack-usergroup-*`` aliases included, are kept so the files move unchanged); it maps to the
neutral ``Schedule``. Each member is a platform account, ``Account("slack", None, <member id>)``.
``load_rotation_schedules`` fails at load on an invalid file, naming it, so a bad file stops boot
instead of surfacing at the first lookup.
"""

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from capabilities.oncall.domain import (
    ROTATIONS,
    Account,
    OnCallPerson,
    Rotation,
    Schedule,
    ScheduleReference,
    shift_windows,
    whos_on,
)
from capabilities.oncall.interfaces import ScheduleSource
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus

ROTATIONS_DIRECTORY = "rotations"
SLACK_PLATFORM = "slack"
DEFAULT_ROTATION_START = datetime(1970, 1, 5, 9, tzinfo=ZoneInfo("America/Toronto"))
_HANDLE_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*")


class RotationFile(BaseModel):
    """One weekly, self-managed rotation as written in its JSON file."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    handle: str = Field(alias="slack-usergroup-handle", min_length=1, description="The rotation's identifier, Slack-handle-safe.")
    name: str = Field(alias="slack-usergroup-name", min_length=1, description="The rotation's display name.")
    members: list[str] = Field(min_length=1, description="Slack user ids, in shift order.")
    rotation_type: Literal["weekly"] = "weekly"
    weeks_per_shift: int = Field(default=1, ge=1, description="Weeks each member stays on call.")
    rotation_start: datetime = Field(default=DEFAULT_ROTATION_START, description="Start of the first shift, with a UTC offset.")

    @field_validator("handle")
    @classmethod
    def _handle_safe(cls, value: str) -> str:
        if not _HANDLE_PATTERN.fullmatch(value):
            raise ValueError("slack-usergroup-handle must be Slack-handle-safe")
        return value

    @field_validator("members")
    @classmethod
    def _members_not_blank(cls, value: list[str]) -> list[str]:
        if any(not member.strip() for member in value):
            raise ValueError("members must not contain blank Slack user IDs")
        return value

    @field_validator("rotation_start")
    @classmethod
    def _start_has_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("rotation_start must include a UTC offset")
        return value

    def to_schedule(self) -> Schedule:
        """Map the file to its schedule: the handle is the reference id, the name the schedule's name."""
        rotation = Rotation(
            name=self.name,
            members=tuple(OnCallPerson(email=None, account=Account(SLACK_PLATFORM, None, member)) for member in self.members),
            weeks_per_shift=self.weeks_per_shift,
            start=self.rotation_start,
        )
        return Schedule(ScheduleReference(ROTATIONS, self.handle), self.name, (rotation,), ())


def load_rotation_schedules(directory: Traversable | None = None) -> tuple[Schedule, ...]:
    """Load and validate every ``*.json`` rotation file of ``directory``, sorted by file name.

    ``directory`` defaults to ``rotations/`` beside the capability; an absent directory is no rotations.

    Raises:
        ValueError: A file is not valid JSON, or two files share a handle.
        pydantic.ValidationError: A file does not match ``RotationFile``.
    """
    directory = directory or files("capabilities.oncall").joinpath(ROTATIONS_DIRECTORY)
    if not directory.is_dir():
        return ()
    parsed: list[RotationFile] = []
    for resource in sorted(directory.iterdir(), key=lambda entry: entry.name):
        if not resource.is_file() or not resource.name.endswith(".json"):
            continue
        try:
            payload = json.loads(resource.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {ROTATIONS_DIRECTORY}/{resource.name}: {exc}") from exc
        parsed.append(RotationFile.model_validate(payload))
    handles = [file.handle for file in parsed]
    duplicates = sorted({handle for handle in handles if handles.count(handle) > 1})
    if duplicates:
        raise ValueError(f"duplicate slack-usergroup-handle values: {duplicates}")
    return tuple(file.to_schedule() for file in parsed)


def _now() -> datetime:
    return datetime.now(UTC)


class RotationsSource(ScheduleSource):
    """``ScheduleSource`` over the loaded rotations; reads memory only, so it never fails on I/O."""

    def __init__(self, schedules: tuple[Schedule, ...], *, clock: Callable[[], datetime] = _now) -> None:
        self._schedules = {schedule.reference.id: schedule for schedule in schedules}
        self._clock = clock

    async def on_call_now(
        self, reference: ScheduleReference, *, rotation: str | None = None
    ) -> OperationResult[tuple[OnCallPerson, ...]]:
        """Return the member on call now; ``rotation`` is ignored, a rotations schedule has one."""
        schedule = self._schedules.get(reference.id)
        if schedule is None:
            return _not_found(reference)
        return OperationResult.success((whos_on(schedule.rotations[0], self._clock()),))

    async def get_schedule(self, reference: ScheduleReference, *, horizon_weeks: int = 12) -> OperationResult[Schedule]:
        """Return the schedule with the active shift and those starting within the horizon."""
        schedule = self._schedules.get(reference.id)
        if schedule is None:
            return _not_found(reference)
        shifts = shift_windows(schedule.rotations[0], self._clock(), horizon_weeks)
        return OperationResult.success(Schedule(schedule.reference, schedule.name, schedule.rotations, shifts))

    async def list_schedules(self) -> OperationResult[tuple[ScheduleReference, ...]]:
        """Return the reference of every loaded rotation."""
        return OperationResult.success(tuple(schedule.reference for schedule in self._schedules.values()))


def _not_found[T](reference: ScheduleReference) -> OperationResult[T]:
    return OperationResult.error(OperationStatus.NOT_FOUND, f"no rotation {reference.id!r}", ErrorCode.NOT_FOUND)
