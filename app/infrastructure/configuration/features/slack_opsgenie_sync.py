"""Slack-OpsGenie sync feature settings."""

import json
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field, field_validator

from infrastructure.configuration.base import FeatureSettings


class OnCallRotation(BaseModel):
    """One OpsGenie rotation mapped to one Slack user group.

    A rotation lives inside an OpsGenie schedule and has exactly one user
    on-call at any given time. The rotation is identified by its name
    (as shown in the OpsGenie UI) rather than its ID, since the rotation
    ID is not exposed in the UI.
    """

    opsgenie_schedule_id: str
    opsgenie_rotation_name: str
    slack_handle: str
    slack_name: str
    slack_description: str = "Auto-synced from OpsGenie"


class SlackOpsGenieSyncSettings(FeatureSettings):
    """Configuration for the OpsGenie -> Slack user-group sync.

    Environment Variables:
        SLACK_OPSGENIE_SYNC_ROTATIONS: JSON list of rotations to sync. When
            empty, the feature is inert. Missing Slack user groups are always
            created automatically.

    Example ``SLACK_OPSGENIE_SYNC_ROTATIONS`` value::

        [
          {
            "opsgenie_schedule_id": "abc-123",
            "opsgenie_rotation_name": "PSO_rotation",
            "slack_handle": "oncall-pso",
            "slack_name": "PSO On-Call"
          }
        ]
    """

    rotations: list[OnCallRotation] = Field(
        default_factory=list, alias="SLACK_OPSGENIE_SYNC_ROTATIONS"
    )

    @field_validator("rotations", mode="before")
    @classmethod
    def _parse_rotations(cls, v: Any) -> Any:
        """Accept either a JSON string or an already-parsed list."""
        if v is None or v == "":
            return []
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(
                    f"Invalid SLACK_OPSGENIE_SYNC_ROTATIONS JSON: {e}"
                ) from e
        return v

    @field_validator("rotations", mode="after")
    @classmethod
    def _validate_unique_handles(cls, v: list[OnCallRotation]) -> list[OnCallRotation]:
        handles = [r.slack_handle for r in v]
        duplicates = {h for h in handles if handles.count(h) > 1}
        if duplicates:
            raise ValueError(
                f"SLACK_OPSGENIE_SYNC_ROTATIONS contains duplicate slack_handle values: "
                f"{sorted(duplicates)}"
            )
        return v


@lru_cache(maxsize=1)
def get_slack_opsgenie_sync_settings() -> SlackOpsGenieSyncSettings:
    """Singleton provider for Slack-OpsGenie sync settings."""
    return SlackOpsGenieSyncSettings()
