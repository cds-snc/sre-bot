"""On-call sync feature settings — colocated with the consuming package.

``OnCallRotation`` and the rotation loader define the declarative mappings
between an on-call rotation (today: OpsGenie) and a messaging-platform user
group (today: Slack). Rotations are loaded from the packaged
``rotations.json`` resource via ``importlib.resources``, so the lookup is
not coupled to the filesystem layout of the repo.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from pydantic import BaseModel, Field, field_validator

ROTATIONS_RESOURCE = "rotations.json"


class OnCallRotation(BaseModel):
    """One on-call rotation mapped to one messaging-platform user group.

    Field names are vendor-prefixed so additional providers (e.g. JSM for
    on-call, MS Teams for messaging) can be added later by introducing
    optional sibling fields without breaking existing rotations.
    """

    opsgenie_schedule_id: str
    opsgenie_rotation_name: str
    slack_handle: str
    slack_name: str
    slack_description: str = "Auto-synced from OpsGenie"


class OnCallRotations(BaseModel):
    """Validated container for the loaded rotations list."""

    rotations: list[OnCallRotation] = Field(default_factory=list)

    @field_validator("rotations", mode="after")
    @classmethod
    def _validate_unique_handles(cls, v: list[OnCallRotation]) -> list[OnCallRotation]:
        handles = [r.slack_handle for r in v]
        duplicates = {h for h in handles if handles.count(h) > 1}
        if duplicates:
            raise ValueError(
                f"rotations.json contains duplicate slack_handle values: "
                f"{sorted(duplicates)}"
            )
        return v


def load_rotations() -> list[OnCallRotation]:
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
    if not isinstance(data, list):
        raise ValueError(
            f"{ROTATIONS_RESOURCE} must contain a JSON list at the top level"
        )
    return OnCallRotations(rotations=data).rotations


@lru_cache(maxsize=1)
def get_oncall_rotations() -> list[OnCallRotation]:
    """Singleton provider for the loaded rotation mappings."""
    return load_rotations()
