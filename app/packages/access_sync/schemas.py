"""Access Sync HTTP request/response schemas.

Pydantic models for FastAPI endpoint validation and serialisation.
These are the only types that cross the HTTP boundary.
"""

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class AccessSyncRequest(BaseModel):
    """Request body for a user sync operation."""

    user_email: EmailStr = Field(..., description="Email of the user to sync.")
    platform: str = Field(
        ..., min_length=2, description="Target platform key, e.g. 'aws'."
    )
    dry_run: bool = Field(
        default=False,
        description="If true, return planned actions without executing them.",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Optional correlation ID for tracing.",
    )


class AccessSyncResponse(BaseModel):
    """Response for a completed (or dry-run) sync operation."""

    success: bool
    message: str
    platform: str
    user_email: str
    dry_run: bool = False
    actions_applied: List[str] = Field(default_factory=list)


class SyncStatusResponse(BaseModel):
    """Summary of the access sync service status."""

    healthy: bool
    registered_platforms: List[str]
