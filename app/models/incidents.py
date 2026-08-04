import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


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
    incident_updates: list[str | dict] | None = []

    model_config = {
        "extra": "forbid",
    }


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
