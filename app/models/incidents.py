import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class Incident(BaseModel):
    """Incident represents an incident record in the incidents table."""

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str
    channel_name: str
    name: str
    user_id: str
    teams: List[str]
    report_url: str
    status: Optional[str] = "Open"
    meet_url: Optional[str] = None
    created_at: Optional[Decimal] = Field(
        default_factory=lambda: Decimal(datetime.now(timezone.utc).timestamp())
    )
    incident_commander: Optional[str] = None
    operations_lead: Optional[str] = None
    severity: Optional[str] = None
    start_impact_time: Optional[Decimal] = None
    end_impact_time: Optional[Decimal] = None
    detection_time: Optional[Decimal] = None
    retrospective_url: Optional[str] = None
    environment: Optional[str] = "prod"
    logs: Optional[List[str | dict]] = []
    incident_updates: Optional[List[str | dict]] = []

    class Config:  # noqa
        extra = "forbid"
