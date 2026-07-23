"""Typed job record models for access sync.

Immutable dataclasses representing the payloads written to and read from the
idempotency store during sync job execution.  Using typed models eliminates
the ``dict[str, Any]`` pattern that caused key-drift across HTTP and Slack
transport modules.

All models are frozen so they cross thread boundaries safely.  ``to_dict()``
converts to the wire representation expected by ``IdempotencyService``.
"""

import dataclasses
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Status and error constants
# ---------------------------------------------------------------------------


class JobStatus:
    """Status string constants used in job and lock records."""

    RUNNING = "running"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncJobError:
    """Sanitized error strings exposed to external callers.

    Internal error details are never surfaced — the external payload always
    uses ``SYNC_FAILED`` so implementation details do not leak through the
    idempotency store or API responses.
    """

    SYNC_FAILED = "sync_failed"


# ---------------------------------------------------------------------------
# Running / lock records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UserRunningRecord:
    """Lock and initial in-progress state for a user sync job.

    Written to both the lock key and the job-id key when a new user sync is
    enqueued.  The lock key copy uses ``status=RUNNING`` so ``check_lock()``
    can detect it; the job-id key copy uses ``status=IN_PROGRESS``.
    """

    job_id: str
    user_email: str
    platform: str
    dry_run: bool
    started_at: str
    sync_type: str = "user"
    status: str = JobStatus.RUNNING

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class PlatformRunningRecord:
    """Lock and initial in-progress state for a platform sync job."""

    job_id: str
    platform: str
    dry_run: bool
    started_at: str
    sync_type: str = "platform"
    status: str = JobStatus.RUNNING

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Completed records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletedUserRecord:
    """Final record for a successfully completed user sync job."""

    job_id: str
    user_email: str
    platform: str
    dry_run: bool
    started_at: str
    completed_at: str
    actions_planned: list[str]
    actions_applied: list[str]
    requires_manual_action: bool
    sync_type: str = "user"
    status: str = JobStatus.COMPLETED

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class CompletedPlatformRecord:
    """Final record for a successfully completed platform sync job."""

    job_id: str
    platform: str
    dry_run: bool
    started_at: str
    completed_at: str
    users_synced: int
    users_converged: int
    orphans_found: int
    requires_manual_action_count: int
    changed_user_count: int = 0
    unchanged_user_count: int = 0
    action_counts: dict[str, int] = dataclasses.field(default_factory=dict)
    lifecycle_actions: dict[str, list[str]] = dataclasses.field(default_factory=dict)
    entitlements_by_action: dict[str, dict[str, list[str]]] = dataclasses.field(default_factory=dict)
    sync_type: str = "platform"
    status: str = JobStatus.COMPLETED

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Failed records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FailedUserRecord:
    """Final record for a failed user sync job.

    ``error`` is always a sanitized string (never raw exception text) so
    internal details do not reach external callers.
    """

    job_id: str
    user_email: str
    platform: str
    dry_run: bool
    started_at: str
    completed_at: str
    error: str
    sync_type: str = "user"
    status: str = JobStatus.FAILED

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class FailedPlatformRecord:
    """Final record for a failed platform sync job."""

    job_id: str
    platform: str
    dry_run: bool
    started_at: str
    completed_at: str
    error: str
    sync_type: str = "platform"
    status: str = JobStatus.FAILED

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------------------
# Union type for type-annotated return sites
# ---------------------------------------------------------------------------

JobRecord = (
    UserRunningRecord
    | PlatformRunningRecord
    | CompletedUserRecord
    | CompletedPlatformRecord
    | FailedUserRecord
    | FailedPlatformRecord
)
