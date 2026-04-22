"""Sync job status presenters.

Maps internal job record dicts (read from the idempotency store) to
transport-appropriate response shapes.  All status formatting logic lives
here so HTTP routes and Slack handlers share a single source of truth for
status strings.
"""

from typing import Any, Dict

import structlog

from infrastructure.services import t
from packages.access.sync.schemas import SyncJobStatusResponse
from packages.access.sync.job_models import JobStatus

logger = structlog.get_logger()


def to_http_status_response(record: Dict[str, Any]) -> SyncJobStatusResponse:
    """Convert a stored job record dict to an HTTP polling response model.

    Extra keys in the record are silently ignored by Pydantic so the schema
    remains stable as new fields are added to job records.
    """
    return SyncJobStatusResponse(**record)


def to_slack_status_message(record: SyncJobStatusResponse, locale: str) -> str:
    """Format a stored job record as a localized Slack status message.

    Uses the ``t()`` i18n helper so messages are rendered in the requesting
    user's locale.  Falls back to inline English strings when a key is absent.
    """
    status = record.status
    job_id = record.job_id
    platform = record.platform
    started_at = record.started_at or ""

    if status == JobStatus.IN_PROGRESS:
        return t(
            "access_sync.status.result.running",
            locale,
            (
                f"\u23f3 Sync job `{job_id}` is *in progress* for platform *{platform}*."
                f"\nStarted: {started_at}"
            ),
            job_id=job_id,
            platform=platform,
            started_at=started_at,
        )

    if status == JobStatus.COMPLETED:
        sync_type = record.sync_type or ""
        completed_at = record.completed_at or ""

        if sync_type == "user":
            user_email = record.user_email or ""
            actions_applied = record.actions_applied or []
            requires_manual = record.requires_manual_action or False
            return t(
                "access_sync.status.result.completed_user",
                locale,
                (
                    f"\u2705 User sync `{job_id}` *completed* for *{user_email}* on *{platform}*."
                    f"\nActions applied: {len(actions_applied)}"
                    + (
                        "\n\u26a0\ufe0f Manual action required"
                        if requires_manual
                        else ""
                    )
                    + f"\nCompleted: {completed_at}"
                ),
                job_id=job_id,
                platform=platform,
                user_email=user_email,
                actions_applied_count=len(actions_applied),
                requires_manual_action=requires_manual,
                completed_at=completed_at,
            )

        users_synced = record.users_synced or 0
        users_converged = record.users_converged or 0
        orphans_found = record.orphans_found or 0
        requires_manual_count = record.requires_manual_action_count or 0
        return t(
            "access_sync.status.result.completed",
            locale,
            (
                f"\u2705 Sync job `{job_id}` *completed* for platform *{platform}*.\n"
                f"Users synced: {users_synced} | Converged: {users_converged} | "
                f"Orphans: {orphans_found} | Manual actions: {requires_manual_count}\n"
                f"Completed: {completed_at}"
            ),
            job_id=job_id,
            platform=platform,
            users_synced=users_synced,
            users_converged=users_converged,
            orphans_found=orphans_found,
            requires_manual_action_count=requires_manual_count,
            completed_at=completed_at,
        )

    if status == JobStatus.FAILED:
        error = record.error or "Unknown error"
        return t(
            "access_sync.status.result.failed",
            locale,
            f"\u274c Sync job `{job_id}` *failed* for platform *{platform}*.\nError: {error}",
            job_id=job_id,
            platform=platform,
            error=error,
        )

    return t(
        "access_sync.status.result.unknown",
        locale,
        f"\u2753 Sync job `{job_id}` has unknown status: *{status}*",
        job_id=job_id,
        status=status,
    )
