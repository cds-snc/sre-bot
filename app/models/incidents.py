import uuid
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class Incident(BaseModel):
    """Incident represents an incident record in the incidents table."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str
    channel_name: str
    name: str
    user_id: str
    teams: List[str]
    report_url: str
    status: str = "Open"
    created_at: str = Field(
        default_factory=lambda: str(datetime.now(timezone.utc).timestamp())
    )
    start_impact_time: str = "Unknown"
    end_impact_time: str = "Unknown"
    detection_time: str = "Unknown"
    environment: str = "prod"
    logs: List[str | dict] = []
    meet_url: Optional[str] = None
    incident_commander: Optional[str] = None
    operations_lead: Optional[str] = None
    severity: Optional[str] = None
    retrospective_url: Optional[str] = None
    incident_updates: Optional[List[str | dict]] = []

    class Config:  # noqa
        extra = "forbid"


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

    class Config:  # noqa
        extra = "forbid"
