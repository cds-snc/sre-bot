"""Access Sync HTTP request/response schemas.

Pydantic models for FastAPI endpoint validation and serialisation.
These are the only types that cross the HTTP boundary.

A single POST /api/v1/access/sync-runs endpoint accepts both sync modes.
The `sync_type` Literal field acts as a Pydantic discriminator so the
correct schema is validated before the request reaches the service layer.
"""

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, EmailStr, Field


class UserSyncRequest(BaseModel):
    """On-demand single-user sync: converge one user on one platform."""

    sync_type: Literal["user"] = "user"
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


class PlatformSyncRequest(BaseModel):
    """Batch platform-wide sync: converge all users on a platform."""

    sync_type: Literal["platform"] = "platform"
    platform: str = Field(
        ..., min_length=2, description="Platform key to sync, e.g. 'aws'."
    )
    dry_run: bool = Field(
        default=False,
        description="If true, return planned actions without executing them.",
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Optional correlation ID for tracing.",
    )


AccessSyncRequest = Annotated[
    Union[UserSyncRequest, PlatformSyncRequest],
    Field(discriminator="sync_type"),
]


class UserSyncResponse(BaseModel):
    """HTTP response for on-demand single-user sync."""

    success: bool
    sync_type: Literal["user"] = "user"
    platform: str
    dry_run: bool = False
    user_email: Optional[str] = None
    actions_planned: List[str] = Field(default_factory=list)
    actions_applied: List[str] = Field(default_factory=list)
    requires_manual_action: bool = False


class PlatformSyncResponse(BaseModel):
    """HTTP response for full platform reconciliation."""

    success: bool
    sync_type: Literal["platform"] = "platform"
    platform: str
    dry_run: bool = False
    users_synced: Optional[int] = None
    users_converged: Optional[int] = None
    orphans_found: Optional[int] = None
    requires_manual_action_count: Optional[int] = None


AccessSyncResponse = Annotated[
    Union[UserSyncResponse, PlatformSyncResponse],
    Field(discriminator="sync_type"),
]
