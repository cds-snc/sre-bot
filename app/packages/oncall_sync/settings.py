"""On-call sync feature settings — colocated with the consuming package.

``OnCallScheduleConfig`` and ``OnCallRotationConfig`` define the declarative
mappings between on-call schedules/rotations (today: OpsGenie) and
messaging-platform user groups (today: Slack). Schedules are loaded from the
packaged ``rotations.json`` resource via ``importlib.resources``, so the lookup
is not coupled to the filesystem layout of the repo.

Each schedule maps to one aggregate user group (containing all currently
on-call users across its rotations) plus one user group per rotation
(containing exactly the one on-call user for that rotation).

The same resource carries the feature-owned ``approved_email_domains`` list,
keeping on-call configuration reviewable in one file instead of an extra
deployment environment variable.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, ValidationError, field_validator, model_validator

ROTATIONS_RESOURCE = "rotations.json"

_EMAIL_ADAPTER: TypeAdapter[str] = TypeAdapter(EmailStr)


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


class OnCallSyncSettings(BaseModel):
    """Feature-owned settings slice sourced from the packaged rotations resource.

    ``APPROVED_EMAIL_DOMAINS`` lists the email domains whose participants may be
    looked up in Slack. An empty list disables filtering entirely.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    APPROVED_EMAIL_DOMAINS: list[str] = Field(default_factory=list, alias="approved_email_domains")

    @field_validator("APPROVED_EMAIL_DOMAINS", mode="after")
    @classmethod
    def _normalize_domains(cls, value: list[str]) -> list[str]:
        domains: list[str] = []
        for entry in value:
            domain = entry.strip().lower()
            if not domain:
                continue
            try:
                _EMAIL_ADAPTER.validate_python(f"oncall@{domain}")
            except ValidationError as exc:
                raise ValueError(f"{ROTATIONS_RESOURCE} contains an invalid approved email domain: {entry!r}") from exc
            domains.append(domain)
        return domains


def _load_rotations_document() -> dict | None:
    """Read the packaged rotations resource, or ``None`` when it is absent."""
    resource = files(__package__).joinpath(ROTATIONS_RESOURCE)
    if not resource.is_file():
        return None
    try:
        data = json.loads(resource.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {ROTATIONS_RESOURCE}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{ROTATIONS_RESOURCE} must contain a JSON object with a 'schedules' key")
    return data


def load_schedules() -> list[OnCallScheduleConfig]:
    """Load and validate the packaged rotations resource.

    Returns an empty list if the resource is missing (feature inactive).
    Raises ``ValueError`` if the resource exists but is malformed.
    """
    data = _load_rotations_document()
    if data is None:
        return []
    if "schedules" not in data:
        raise ValueError(f"{ROTATIONS_RESOURCE} must contain a JSON object with a 'schedules' key")
    return OnCallSchedules(schedules=data["schedules"]).schedules


def load_sync_settings() -> OnCallSyncSettings:
    """Load the feature settings slice from the packaged rotations resource."""
    data = _load_rotations_document()
    if data is None:
        return OnCallSyncSettings()
    return OnCallSyncSettings.model_validate(data)


@lru_cache(maxsize=1)
def get_oncall_schedules() -> list[OnCallScheduleConfig]:
    """Singleton provider for the loaded schedule configurations."""
    return load_schedules()


@lru_cache(maxsize=1)
def get_oncall_sync_settings() -> OnCallSyncSettings:
    """Singleton provider for the on-call sync settings slice."""
    return load_sync_settings()
