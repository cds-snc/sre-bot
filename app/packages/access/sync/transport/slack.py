"""Slack platform integration for Access Sync.

Command hierarchy under /sre:
    sre
    └── access               (parent — shared by all access subpackages)
        └── sync             (parent)
            ├── user  <user_email> <platform> [--dry-run]
            ├── platform  <platform> [--dry-run]
            └── status  <job_id>
"""

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, TYPE_CHECKING

import structlog

from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.platforms.parsing import Argument, ArgumentType
from infrastructure.services import get_idempotency_service, t
from packages.access.sync.providers import (
    get_access_sync_coordinator,
    get_access_sync_settings,
)
from packages.access.sync.platform_lock import (
    acquire_lock,
    check_lock,
    platform_lock_key,
    release_lock,
    user_lock_key,
)

if TYPE_CHECKING:
    from infrastructure.platforms.providers.slack import SlackPlatformProvider

logger = structlog.get_logger()


def register_commands(provider: "SlackPlatformProvider") -> None:
    """Register access sync Slack commands.

    Registers the ``access`` parent (shared by all access subpackages), the
    ``sync`` sub-parent, and three leaf commands for user sync, platform sync,
    and job-status polling.
    """
    # access parent — handler=None lets the framework auto-generate help.
    # Other access subpackages (catalog, admin, request) use parent="sre.access"
    # and the framework creates this node automatically if not yet registered.
    provider.register_command(
        command="access",
        handler=None,
        parent="sre",
        description="Access management commands",
        description_key="access.description",
    )

    # sync parent
    provider.register_command(
        command="sync",
        handler=None,
        parent="sre.access",
        description="Access sync commands",
        description_key="access_sync.description",
    )

    # sync user — synchronous, bilingual summary
    provider.register_command(
        command="user",
        handler=handle_sync_user_command,
        parent="sre.access.sync",
        description="Sync a single user's access on a platform",
        description_key="access_sync.user.description",
        usage_hint="<user_email> <platform> [--dry-run]",
        examples=[
            "user@example.com aws",
            "user@example.com aws --dry-run",
        ],
        example_keys=[
            "access_sync.examples.sync_user",
            "access_sync.examples.sync_user_dry_run",
        ],
        arguments=[
            Argument(
                name="user_email",
                type=ArgumentType.STRING,
                required=True,
                description="Email address of the user to sync",
            ),
            Argument(
                name="platform",
                type=ArgumentType.STRING,
                required=True,
                description="Target platform key (e.g. aws)",
            ),
            Argument(
                name="--dry-run",
                type=ArgumentType.BOOLEAN,
                required=False,
                description="Preview planned actions without executing",
            ),
        ],
    )

    # sync platform — enqueues background job, returns job_id immediately
    provider.register_command(
        command="platform",
        handler=handle_sync_platform_command,
        parent="sre.access.sync",
        description="Enqueue a full platform-wide access sync job",
        description_key="access_sync.platform.description",
        usage_hint="<platform> [--dry-run]",
        examples=[
            "aws",
            "aws --dry-run",
        ],
        example_keys=[
            "access_sync.examples.sync_platform",
            "access_sync.examples.sync_platform_dry_run",
        ],
        arguments=[
            Argument(
                name="platform",
                type=ArgumentType.STRING,
                required=True,
                description="Target platform key (e.g. aws)",
            ),
            Argument(
                name="--dry-run",
                type=ArgumentType.BOOLEAN,
                required=False,
                description="Preview planned actions without executing",
            ),
        ],
    )

    # sync status — polls job status from idempotency store
    provider.register_command(
        command="status",
        handler=handle_sync_status_command,
        parent="sre.access.sync",
        description="Check the status of a platform sync job",
        description_key="access_sync.status.description",
        usage_hint="<job_id>",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
        example_keys=["access_sync.examples.sync_status"],
        arguments=[
            Argument(
                name="job_id",
                type=ArgumentType.STRING,
                required=True,
                description="Job ID returned by the platform sync command",
            ),
        ],
    )


def _run_user_sync_background(
    coordinator: Any,
    job_id: str,
    user_email: str,
    platform: str,
    dry_run: bool,
    started_at: str,
    job_ttl_seconds: int,
) -> None:
    """Background thread target: run user sync and persist the outcome."""
    idempotency = get_idempotency_service()
    log = logger.bind(
        job_id=job_id, user_email=user_email, platform=platform, dry_run=dry_run
    )

    payload: Dict[str, Any]
    try:
        result = coordinator.sync_user(
            user_email=user_email,
            platform=platform,
            dry_run=dry_run,
            request_id=job_id,
        )

        if result.is_success and result.data is not None:
            outcome = result.data
            payload = {
                "job_id": job_id,
                "sync_type": "user",
                "user_email": user_email,
                "platform": platform,
                "dry_run": dry_run,
                "status": "completed",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "actions_planned": outcome.planned_actions,
                "actions_applied": outcome.applied_actions,
                "requires_manual_action": outcome.requires_manual_action,
            }
            log.info(
                "user_sync_job_completed",
                applied=len(outcome.applied_actions),
            )
        else:
            payload = {
                "job_id": job_id,
                "sync_type": "user",
                "user_email": user_email,
                "platform": platform,
                "dry_run": dry_run,
                "status": "failed",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": result.message or "Sync returned no outcome",
            }
            log.warning("user_sync_job_failed", error=result.message)

    except Exception as exc:
        payload = {
            "job_id": job_id,
            "sync_type": "user",
            "user_email": user_email,
            "platform": platform,
            "dry_run": dry_run,
            "status": "failed",
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": "sync_failed",
        }
        log.error("user_sync_job_error", error=str(exc), error_type=type(exc).__name__)

    idempotency.set(job_id, payload, ttl_seconds=job_ttl_seconds)
    release_lock(
        user_lock_key(platform, user_email), payload, idempotency, job_ttl_seconds
    )


def handle_sync_user_command(
    payload: CommandPayload,
    parsed_args: Dict[str, Any],
) -> CommandResponse:
    """Handle /sre access sync user <user_email> <platform> [--dry-run].

    Runs synchronously and returns a bilingual summary of applied actions.
    """
    locale = getattr(payload, "user_locale", None) or "en-US"
    user_email = str(parsed_args.get("user_email", "")).strip().lower()
    platform = str(parsed_args.get("platform", "")).strip().lower()
    dry_run = bool(parsed_args.get("--dry-run", False))

    log = logger.bind(
        command="access.sync.user",
        user_id=payload.user_id,
        channel_id=payload.channel_id,
        user_email=user_email,
        platform=platform,
        dry_run=dry_run,
    )
    log.info("slack_command_received", text=payload.text)

    coordinator = get_access_sync_coordinator()
    idempotency = get_idempotency_service()
    settings = get_access_sync_settings()
    job_ttl = settings.sync_job_ttl_seconds
    lock_stale = settings.sync_lock_stale_after_seconds

    lock_key = user_lock_key(platform, user_email)
    running = check_lock(lock_key, idempotency, lock_stale)
    if running is not None:
        existing_job_id = running.get("job_id", "")
        log.info("user_sync_already_running", existing_job_id=existing_job_id)
        return CommandResponse(
            message=t(
                "access_sync.user.result.already_running",
                locale,
                (
                    f"⏳ User sync already in progress for *{user_email}* on *{platform}*."
                    f"\nJob ID: `{existing_job_id}`"
                    f"\nPoll status: `/sre access sync status {existing_job_id}`"
                ),
                user_email=user_email,
                platform=platform,
                job_id=existing_job_id,
            ),
            ephemeral=True,
        )

    job_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    acquire_lock(
        lock_key,
        {
            "job_id": job_id,
            "sync_type": "user",
            "user_email": user_email,
            "platform": platform,
            "dry_run": dry_run,
            "status": "running",
            "started_at": started_at,
        },
        idempotency,
        job_ttl,
    )
    idempotency.set(
        job_id,
        {
            "job_id": job_id,
            "sync_type": "user",
            "user_email": user_email,
            "platform": platform,
            "dry_run": dry_run,
            "status": "in_progress",
            "started_at": started_at,
        },
        ttl_seconds=job_ttl,
    )

    thread = threading.Thread(
        target=_run_user_sync_background,
        kwargs=dict(
            coordinator=coordinator,
            job_id=job_id,
            user_email=user_email,
            platform=platform,
            dry_run=dry_run,
            started_at=started_at,
            job_ttl_seconds=job_ttl,
        ),
        daemon=True,
    )
    thread.start()

    log.info("user_sync_job_enqueued", job_id=job_id)

    return CommandResponse(
        message=t(
            "access_sync.user.result.enqueued",
            locale,
            (
                f"⏳ User sync enqueued for *{user_email}* on *{platform}*."
                f"\nJob ID: `{job_id}`"
                f"\nPoll status: `/sre access sync status {job_id}`"
            ),
            user_email=user_email,
            platform=platform,
            job_id=job_id,
        ),
        ephemeral=False,
    )


def _run_platform_sync_background(
    coordinator: Any,
    job_id: str,
    platform: str,
    dry_run: bool,
    started_at: str,
    job_ttl_seconds: int,
) -> None:
    """Background thread target: run platform sync and persist the outcome."""
    idempotency = get_idempotency_service()
    log = logger.bind(job_id=job_id, platform=platform, dry_run=dry_run)

    payload: Dict[str, Any]
    try:
        result = coordinator.sync_platform(
            platform=platform,
            dry_run=dry_run,
            request_id=job_id,
        )

        if result.is_success and result.data is not None:
            outcome = result.data
            payload = {
                "job_id": job_id,
                "platform": platform,
                "dry_run": dry_run,
                "status": "completed",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "users_synced": outcome.users_synced,
                "users_converged": outcome.users_converged,
                "orphans_found": outcome.orphans_found,
                "requires_manual_action_count": outcome.requires_manual_action_count,
            }
            log.info(
                "platform_sync_job_completed",
                users_synced=outcome.users_synced,
                users_converged=outcome.users_converged,
                orphans_found=outcome.orphans_found,
                requires_manual_action_count=outcome.requires_manual_action_count,
            )
        else:
            payload = {
                "job_id": job_id,
                "platform": platform,
                "dry_run": dry_run,
                "status": "failed",
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": result.message or "Sync returned no outcome",
            }
            log.warning("platform_sync_job_failed", error=result.message)

    except Exception as exc:
        payload = {
            "job_id": job_id,
            "platform": platform,
            "dry_run": dry_run,
            "status": "failed",
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": "sync_failed",
        }
        log.error(
            "platform_sync_job_error", error=str(exc), error_type=type(exc).__name__
        )

    idempotency.set(job_id, payload, ttl_seconds=job_ttl_seconds)
    release_lock(platform_lock_key(platform), payload, idempotency, job_ttl_seconds)


def handle_sync_platform_command(
    payload: CommandPayload,
    parsed_args: Dict[str, Any],
) -> CommandResponse:
    """Handle /sre access sync platform <platform> [--dry-run].

    Enqueues a background sync job and returns the job ID immediately so the
    operator can poll status with ``/sre access sync status <job_id>``.
    """
    locale = getattr(payload, "user_locale", None) or "en-US"
    platform = str(parsed_args.get("platform", "")).strip().lower()
    dry_run = bool(parsed_args.get("--dry-run", False))

    log = logger.bind(
        command="access.sync.platform",
        user_id=payload.user_id,
        channel_id=payload.channel_id,
        platform=platform,
        dry_run=dry_run,
    )
    log.info("slack_command_received", text=payload.text)

    coordinator = get_access_sync_coordinator()
    idempotency = get_idempotency_service()
    settings = get_access_sync_settings()
    job_ttl = settings.sync_job_ttl_seconds
    lock_stale = settings.sync_lock_stale_after_seconds

    running = check_lock(platform_lock_key(platform), idempotency, lock_stale)
    if running is not None:
        existing_job_id = running.get("job_id", "")
        log.info("platform_sync_already_running", existing_job_id=existing_job_id)
        return CommandResponse(
            message=t(
                "access_sync.platform.result.already_running",
                locale,
                (
                    f"⏳ Platform sync already in progress for *{platform}*."
                    f"\nJob ID: `{existing_job_id}`"
                    f"\nPoll status: `/sre access sync status {existing_job_id}`"
                ),
                platform=platform,
                job_id=existing_job_id,
            ),
            ephemeral=True,
        )

    job_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    acquire_lock(
        platform_lock_key(platform),
        {
            "job_id": job_id,
            "platform": platform,
            "dry_run": dry_run,
            "status": "running",
            "started_at": started_at,
        },
        idempotency,
        job_ttl,
    )
    idempotency.set(
        job_id,
        {
            "job_id": job_id,
            "platform": platform,
            "dry_run": dry_run,
            "status": "in_progress",
            "started_at": started_at,
        },
        ttl_seconds=job_ttl,
    )

    thread = threading.Thread(
        target=_run_platform_sync_background,
        kwargs=dict(
            coordinator=coordinator,
            job_id=job_id,
            platform=platform,
            dry_run=dry_run,
            started_at=started_at,
            job_ttl_seconds=job_ttl,
        ),
        daemon=True,
    )
    thread.start()

    log.info("platform_sync_job_enqueued", job_id=job_id)

    return CommandResponse(
        message=t(
            "access_sync.platform.result.enqueued",
            locale,
            (
                f"✅ Platform sync job enqueued for *{platform}*.\n"
                f"Job ID: `{job_id}`\n"
                f"Poll status: `/sre access sync status {job_id}`"
            ),
            platform=platform,
            job_id=job_id,
        ),
        ephemeral=False,
    )


def handle_sync_status_command(
    payload: CommandPayload,
    parsed_args: Dict[str, Any],
) -> CommandResponse:
    """Handle /sre access sync status <job_id>.

    Reads the job record from the idempotency store and returns a formatted
    status message.
    """
    locale = getattr(payload, "user_locale", None) or "en-US"
    job_id = str(parsed_args.get("job_id", "")).strip()

    log = logger.bind(
        command="access.sync.status",
        user_id=payload.user_id,
        channel_id=payload.channel_id,
        job_id=job_id,
    )
    log.info("slack_command_received", text=payload.text)

    idempotency = get_idempotency_service()
    record = idempotency.get(job_id)

    if record is None:
        return CommandResponse(
            message=t(
                "access_sync.status.result.not_found",
                locale,
                f"⚠️ No sync job found with ID: `{job_id}`",
                job_id=job_id,
            ),
            ephemeral=True,
        )

    status = record.get("status", "unknown")
    platform = record.get("platform", "")
    started_at = record.get("started_at", "")

    if status == "running":
        message = t(
            "access_sync.status.result.running",
            locale,
            f"⏳ Sync job `{job_id}` is *running* for platform *{platform}*.\nStarted: {started_at}",
            job_id=job_id,
            platform=platform,
            started_at=started_at,
        )

    elif status == "completed":
        users_synced = record.get("users_synced", 0)
        users_converged = record.get("users_converged", 0)
        orphans_found = record.get("orphans_found", 0)
        requires_manual = record.get("requires_manual_action_count", 0)
        completed_at = record.get("completed_at", "")
        message = t(
            "access_sync.status.result.completed",
            locale,
            (
                f"✅ Sync job `{job_id}` *completed* for platform *{platform}*.\n"
                f"Users synced: {users_synced} | Converged: {users_converged} | "
                f"Orphans: {orphans_found} | Manual actions: {requires_manual}\n"
                f"Completed: {completed_at}"
            ),
            job_id=job_id,
            platform=platform,
            users_synced=users_synced,
            users_converged=users_converged,
            orphans_found=orphans_found,
            requires_manual_action_count=requires_manual,
            completed_at=completed_at,
        )

    elif status == "failed":
        error = record.get("error", "Unknown error")
        message = t(
            "access_sync.status.result.failed",
            locale,
            f"❌ Sync job `{job_id}` *failed* for platform *{platform}*.\nError: {error}",
            job_id=job_id,
            platform=platform,
            error=error,
        )

    else:
        message = t(
            "access_sync.status.result.unknown",
            locale,
            f"❓ Sync job `{job_id}` has unknown status: *{status}*",
            job_id=job_id,
            status=status,
        )

    return CommandResponse(message=message, ephemeral=True)
