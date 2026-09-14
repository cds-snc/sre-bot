"""Configuration for self-managed, JSON-backed Slack UserGroup rotations."""

import json
import re
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

ROTATIONS_DIRECTORY = "rotations"
DEFAULT_ROTATION_START = datetime(1970, 1, 5, 9, tzinfo=ZoneInfo("America/Toronto"))
_HANDLE_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*")


class RotationConfig(BaseModel):
    """One weekly, self-managed rotation linked to a Slack UserGroup."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    slack_usergroup_handle: str = Field(alias="slack-usergroup-handle", min_length=1)
    slack_usergroup_name: str = Field(alias="slack-usergroup-name", min_length=1)
    members: list[str] = Field(min_length=1)
    rotation_type: Literal["weekly"] = "weekly"
    weeks_per_shift: int = Field(default=1, ge=1)
    rotation_start: datetime = DEFAULT_ROTATION_START

    @field_validator("slack_usergroup_handle")
    @classmethod
    def validate_slack_usergroup_handle(cls, value: str) -> str:
        if not _HANDLE_PATTERN.fullmatch(value):
            raise ValueError("slack-usergroup-handle must be Slack-handle-safe")
        return value

    @field_validator("members")
    @classmethod
    def validate_members(cls, value: list[str]) -> list[str]:
        if any(not member.strip() for member in value):
            raise ValueError("members must not contain blank Slack user IDs")
        return value

    @field_validator("rotation_start")
    @classmethod
    def validate_rotation_start(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("rotation_start must include a UTC offset")
        return value


def load_rotations() -> list[RotationConfig]:
    """Load and validate the JSON file for each configured rotation."""
    rotations_directory = files(__package__).joinpath(ROTATIONS_DIRECTORY)
    if not rotations_directory.is_dir():
        return []

    rotations: list[RotationConfig] = []
    for resource in sorted(rotations_directory.iterdir(), key=lambda entry: entry.name):
        if not resource.is_file() or not resource.name.endswith(".json"):
            continue
        try:
            payload = json.loads(resource.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {ROTATIONS_DIRECTORY}/{resource.name}: {exc}") from exc
        rotations.append(RotationConfig.model_validate(payload))

    handles = [rotation.slack_usergroup_handle for rotation in rotations]
    duplicates = sorted({handle for handle in handles if handles.count(handle) > 1})
    if duplicates:
        raise ValueError(f"duplicate slack-usergroup-handle values: {duplicates}")
    return rotations


@lru_cache(maxsize=1)
def get_rotations() -> list[RotationConfig]:
    """Return the singleton collection of configured rotations."""
    return load_rotations()
