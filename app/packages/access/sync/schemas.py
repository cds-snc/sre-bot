"""Access Sync HTTP request/response schemas.

Pydantic models for FastAPI endpoint validation and serialisation.
These are the only types that cross the HTTP boundary.

A single POST /api/v1/access/sync-runs endpoint accepts both sync modes.
The `sync_type` Literal field acts as a Pydantic discriminator so the
correct schema is validated before the request reaches the service layer.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field


class UserSyncRequest(BaseModel):
    """On-demand single-user sync: converge one user on one platform."""

    sync_type: Literal["user"] = "user"
    user_email: EmailStr = Field(..., description="Email of the user to sync.")
    platform: str = Field(..., min_length=2, description="Target platform key, e.g. 'aws'.")
    dry_run: bool = Field(
        default=False,
        description="If true, return planned actions without executing them.",
    )
    request_id: str | None = Field(
        default=None,
        description="Optional correlation ID for tracing.",
    )


class PlatformSyncRequest(BaseModel):
    """Batch platform-wide sync: converge all users on a platform."""

    sync_type: Literal["platform"] = "platform"
    platform: str = Field(..., min_length=2, description="Platform key to sync, e.g. 'aws'.")
    dry_run: bool = Field(
        default=False,
        description="If true, return planned actions without executing them.",
    )
    request_id: str | None = Field(
        default=None,
        description="Optional correlation ID for tracing.",
    )


AccessSyncRequest = Annotated[
    UserSyncRequest | PlatformSyncRequest,
    Field(discriminator="sync_type"),
]


class PlatformSyncJobAcceptedResponse(BaseModel):
    """HTTP 202 response when a platform sync job is enqueued."""

    success: bool
    sync_type: Literal["platform"] = "platform"
    job_id: str
    platform: str
    dry_run: bool = False
    status: Literal["in_progress"] = "in_progress"
    started_at: str


class UserSyncJobAcceptedResponse(BaseModel):
    """HTTP 202 response when a user sync job is enqueued."""

    success: bool
    sync_type: Literal["user"] = "user"
    job_id: str
    platform: str
    user_email: str
    dry_run: bool = False
    status: Literal["in_progress"] = "in_progress"
    started_at: str


class SyncJobStatusResponse(BaseModel):
    """Polling response for any enqueued sync job (user or platform).

    Job-type-specific fields are optional so the same schema serves both
    user sync and platform sync jobs without requiring separate polling models.
    """

    job_id: str
    sync_type: str | None = None
    platform: str
    dry_run: bool
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    # Platform sync outcome fields
    users_synced: int | None = None
    users_converged: int | None = None
    orphans_found: int | None = None
    requires_manual_action_count: int | None = None
    changed_user_count: int | None = None
    unchanged_user_count: int | None = None
    action_counts: dict[str, int] | None = None
    lifecycle_actions: dict[str, list[str]] | None = None
    entitlements_by_action: dict[str, dict[str, list[str]]] | None = None
    # User sync outcome fields
    user_email: str | None = None
    actions_planned: list[str] | None = None
    actions_applied: list[str] | None = None
    requires_manual_action: bool | None = None
