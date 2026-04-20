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

from infrastructure.operations import OperationStatus
from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.platforms.parsing import Argument, ArgumentType
from infrastructure.services import get_idempotency_service, t
from packages.access.sync.providers import (
    get_access_sync_coordinator,
)

if TYPE_CHECKING:
    from infrastructure.platforms.providers.slack import SlackPlatformProvider

logger = structlog.get_logger()

# TTL for platform sync job records in the idempotency store (24 h)
_PLATFORM_SYNC_JOB_TTL_SECONDS = 86400


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
    result = coordinator.sync_user(
        user_email=user_email,
        platform=platform,
        dry_run=dry_run,
        request_id=getattr(payload, "correlation_id", "") or "",
    )

    if result.is_success:
        outcome = result.data
        applied_actions = outcome.applied_actions if outcome else []

        if dry_run:
            prefix = t(
                "access_sync.user.result.dry_run_prefix",
                locale,
                "Dry-run — planned actions",
            )
        else:
            prefix = t(
                "access_sync.user.result.sync_prefix",
                locale,
                "Sync complete — actions applied",
            )

        if applied_actions:
            actions_text = "\n".join(f"• `{a}`" for a in applied_actions)
        else:
            actions_text = t(
                "access_sync.user.result.no_actions",
                locale,
                "_(none)_",
            )

        manual_note = ""
        if outcome and outcome.requires_manual_action:
            manual_note = "\n" + t(
                "access_sync.user.result.manual_action_required",
                locale,
                "⚠️ Some actions require manual follow-up.",
            )

        message = (
            f"{prefix} for *{user_email}* on *{platform}*:\n"
            f"{actions_text}{manual_note}"
        )
        return CommandResponse(message=message, ephemeral=False)

    if result.status == OperationStatus.NOT_FOUND:
        return CommandResponse(
            message=t(
                "access_sync.user.result.not_found",
                locale,
                f"⚠️ User or platform not found: {result.message}",
                message=result.message,
            ),
            ephemeral=True,
        )

    return CommandResponse(
        message=t(
            "access_sync.user.result.error",
            locale,
            f"❌ Sync failed: {result.message}",
            message=result.message,
        ),
        ephemeral=True,
    )


def _run_platform_sync_background(
    coordinator: Any,
    job_id: str,
    platform: str,
    dry_run: bool,
    started_at: str,
) -> None:
    """Background thread target: run platform sync and persist the outcome.

    The idempotency record is written to ``running`` before this thread starts.
    This function overwrites it with ``completed`` or ``failed`` once the
    coordinator returns.
    """
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
            "error": str(exc),
        }
        log.error("platform_sync_job_error", error=str(exc))

    idempotency.set(job_id, payload, ttl_seconds=_PLATFORM_SYNC_JOB_TTL_SECONDS)


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

    job_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()

    coordinator = get_access_sync_coordinator()
    idempotency = get_idempotency_service()

    # Persist running status before spawning the thread so polling works immediately
    idempotency.set(
        job_id,
        {
            "job_id": job_id,
            "platform": platform,
            "dry_run": dry_run,
            "status": "running",
            "phase": "syncing",
            "started_at": started_at,
        },
        ttl_seconds=_PLATFORM_SYNC_JOB_TTL_SECONDS,
    )

    thread = threading.Thread(
        target=_run_platform_sync_background,
        kwargs=dict(
            coordinator=coordinator,
            job_id=job_id,
            platform=platform,
            dry_run=dry_run,
            started_at=started_at,
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
