"""Self-managed weekly rotation selection and current-assignment lookup."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from packages.user_rotations.settings import RotationConfig


@dataclass(frozen=True)
class CurrentUserRotation:
    """The current Slack user assignment for one configured rotation."""

    slack_usergroup_handle: str
    slack_usergroup_name: str
    slack_user_id: str


@dataclass(frozen=True)
class UserRotationShift:
    """One scheduled user-rotation shift."""

    slack_user_id: str
    start: datetime
    end: datetime


def whos_on(rotation: RotationConfig, t: datetime | None = None) -> str:
    """Return the configured member responsible at a given time."""
    current_time = t or datetime.now(UTC)
    period = timedelta(weeks=rotation.weeks_per_shift)
    index = int((current_time - rotation.rotation_start) // period) % len(rotation.members)
    return rotation.members[index]


class UserRotationsService:
    """Provide current assignments for the configured rotations."""

    def __init__(self, *, rotations: Iterable[RotationConfig]) -> None:
        self._rotations = list(rotations)

    def get_current_rotations(self, t: datetime | None = None) -> list[CurrentUserRotation]:
        """Return the current Slack user assignment for every rotation."""
        return [
            CurrentUserRotation(
                slack_usergroup_handle=rotation.slack_usergroup_handle,
                slack_usergroup_name=rotation.slack_usergroup_name,
                slack_user_id=whos_on(rotation, t=t),
            )
            for rotation in self._rotations
        ]

    def get_rotation_shifts(
        self,
        handle: str,
    ) -> list[UserRotationShift] | None:
        """Return the active shift and shifts starting in the next 12 weeks."""
        rotation = next((rotation for rotation in self._rotations if rotation.slack_usergroup_handle == handle), None)
        if rotation is None:
            return None

        current_time = datetime.now(UTC)
        period = timedelta(weeks=rotation.weeks_per_shift)
        shift_start = rotation.rotation_start + int((current_time - rotation.rotation_start) // period) * period
        end_time = current_time + timedelta(weeks=12)
        shifts: list[UserRotationShift] = []
        while shift_start < end_time:
            shifts.append(UserRotationShift(whos_on(rotation, shift_start), shift_start, shift_start + period))
            shift_start += period
        return shifts
