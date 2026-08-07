"""On-call sync feature settings — colocated with the consuming package.

``OnCallScheduleConfig`` and ``OnCallRotationConfig`` define the declarative
mappings between on-call schedules/rotations (today: OpsGenie) and
messaging-platform user groups (today: Slack). Schedules are loaded from the
packaged ``rotations.json`` resource via ``importlib.resources``, so the lookup
is not coupled to the filesystem layout of the repo.

Each schedule maps to one aggregate user group (containing all currently
on-call users across its rotations) plus one user group per rotation
(containing exactly the one on-call user for that rotation).
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from pydantic import BaseModel, Field, model_validator

ROTATIONS_RESOURCE = "rotations.json"


class OnCallRotationConfig(BaseModel):
    """One on-call rotation within a schedule, mapped to a messaging-platform user group.

    The parent schedule's ``opsgenie_schedule_id`` is resolved at runtime by
    the service when constructing the flat ``OnCallRotation`` passed to adapters.
    """

    opsgenie_rotation_name: str
    slack_handle: str
    slack_name: str
    slack_description: str = "Auto-synced from OpsGenie"


class OnCallScheduleConfig(BaseModel):
    """An on-call schedule with its child rotations and an aggregate user group.

    The ``slack_handle`` / ``slack_name`` fields (vendor-prefixed) describe the
    schedule-level aggregate user group, which mirrors all currently on-call
    users across every rotation in this schedule.
    """

    opsgenie_schedule_id: str
    slack_handle: str
    slack_name: str
    slack_description: str = "Auto-synced from OpsGenie"
    rotations: list[OnCallRotationConfig] = Field(default_factory=list)


class OnCallSchedules(BaseModel):
    """Validated container for the loaded schedules."""

    schedules: list[OnCallScheduleConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_handles(self) -> OnCallSchedules:
        handles: list[str] = []
        for schedule in self.schedules:
            handles.append(schedule.slack_handle)
            handles.extend(r.slack_handle for r in schedule.rotations)
        duplicates = {h for h in handles if handles.count(h) > 1}
        if duplicates:
            raise ValueError(f"rotations.json contains duplicate slack_handle values: {sorted(duplicates)}")
        return self


# ---------------------------------------------------------------------------
# Flat rotation type — passed to ports and adapters
# ---------------------------------------------------------------------------


class OnCallRotation(BaseModel):
    """Runtime-resolved rotation with its parent schedule ID baked in.

    Constructed by the service from ``OnCallScheduleConfig`` +
    ``OnCallRotationConfig``; passed to the ``OnCallScheduleProvider`` and
    ``UserGroupSyncTarget`` adapters. Field names are vendor-prefixed so
    additional providers can be added later without breaking existing rotations.
    """

    opsgenie_schedule_id: str
    opsgenie_rotation_name: str
    slack_handle: str
    slack_name: str
    slack_description: str = "Auto-synced from OpsGenie"


def load_schedules() -> list[OnCallScheduleConfig]:
    """Load and validate the packaged rotations resource.

    Returns an empty list if the resource is missing (feature inactive).
    Raises ``ValueError`` if the resource exists but is malformed.
    """
    resource = files(__package__).joinpath(ROTATIONS_RESOURCE)
    if not resource.is_file():
        return []
    try:
        data = json.loads(resource.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {ROTATIONS_RESOURCE}: {exc}") from exc
    if not isinstance(data, dict) or "schedules" not in data:
        raise ValueError(f"{ROTATIONS_RESOURCE} must contain a JSON object with a 'schedules' key")
    return OnCallSchedules(schedules=data["schedules"]).schedules


@lru_cache(maxsize=1)
def get_oncall_schedules() -> list[OnCallScheduleConfig]:
    """Singleton provider for the loaded schedule configurations."""
    return load_schedules()
