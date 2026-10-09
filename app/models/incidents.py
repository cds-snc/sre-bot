import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

_RETIRED_INCIDENT_UPDATES_KEY = "incident_updates"


class Incident(BaseModel):
    """Incident represents an incident record in the incidents table."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str
    channel_name: str
    name: str
    user_id: str
    teams: list[str]
    report_url: str
    status: str = "Open"
    created_at: str = Field(default_factory=lambda: str(datetime.now(UTC).timestamp()))
    start_impact_time: str = "Unknown"
    end_impact_time: str = "Unknown"
    detection_time: str = "Unknown"
    environment: str = "prod"
    logs: list[str | dict] = []
    meet_url: str | None = None
    incident_commander: str | None = None
    operations_lead: str | None = None
    severity: str | None = None
    retrospective_url: str | None = None
    security_incident: bool | None = None

    model_config = {
        "extra": "forbid",
    }

    @model_validator(mode="before")
    @classmethod
    def _drop_retired_incident_updates(cls, data: Any) -> Any:
        """Tolerate stored rows that still carry the retired ``incident_updates`` attribute."""
        if isinstance(data, dict) and _RETIRED_INCIDENT_UPDATES_KEY in data:
            return {key: value for key, value in data.items() if key != _RETIRED_INCIDENT_UPDATES_KEY}
        return data


class IncidentPayload(BaseModel):
    """IncidentPayload represents the payload received from the Slack modal."""

    name: str
    folder: str
    product: str
    security_incident: str
    user_id: str
    channel_id: str
    channel_name: str
    slug: str
    severity: str | None = None
    source_alert_permalink: str | None = None

    model_config = {
        "extra": "forbid",
    }
