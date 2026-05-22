"""Slack platform integration for Access Sync.

Command hierarchy under /sre:
    sre
    └── access               (parent — shared by all access subpackages)
        └── sync             (parent)
            ├── user  <user_email> <platform> [--dry-run]
            ├── platform  <platform> [--dry-run]
            └── status  <job_id>
"""

from typing import TYPE_CHECKING, Any, Dict

import structlog

from infrastructure.i18n import t
from infrastructure.idempotency import get_idempotency_service
from infrastructure.platforms.parsing import Argument, ArgumentType
from integrations.slack.models import CommandPayload, CommandResponse
from packages.access.sync.interactions.ingress import (
    enqueue_platform_sync,
    enqueue_user_sync,
)
from packages.access.sync.presenters import to_slack_status_message
from packages.access.sync.providers import (
    get_access_sync_coordinator,
    get_access_sync_settings,
)
from packages.access.sync.schemas import SyncJobStatusResponse

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

    # sync user — enqueues background job, returns job_id immediately
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

    Enqueues a background user sync job and returns the job ID immediately.
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

    result = enqueue_user_sync(
        coordinator=coordinator,
        idempotency=idempotency,
        settings=settings,
        user_email=user_email,
        platform=platform,
        dry_run=dry_run,
    )

    if not result.is_success or result.data is None:
        if result.error_code == "FEATURE_DISABLED":
            log.warning("access_sync_disabled_rejected")
            return CommandResponse(
                message=t(
                    "access_sync.disabled",
                    locale,
                    "\u26d4 Access Sync is not enabled. Contact your administrator.",
                ),
                ephemeral=True,
            )
        return CommandResponse(
            message=t(
                "access_sync.user.result.error",
                locale,
                f"\u274c Unexpected error: {result.message}",
            ),
            ephemeral=True,
        )

    job = result.data
    if job.already_running:
        log.info("user_sync_already_running", existing_job_id=job.job_id)
        return CommandResponse(
            message=t(
                "access_sync.user.result.already_running",
                locale,
                (
                    f"\u23f3 User sync already in progress for *{user_email}* on *{platform}*."
                    f"\nJob ID: `{job.job_id}`"
                    f"\nPoll status: `/sre access sync status {job.job_id}`"
                ),
                user_email=user_email,
                platform=platform,
                job_id=job.job_id,
            ),
            ephemeral=True,
        )

    log.info("user_sync_job_enqueued", job_id=job.job_id)
    return CommandResponse(
        message=t(
            "access_sync.user.result.enqueued",
            locale,
            (
                f"\u23f3 User sync enqueued for *{user_email}* on *{platform}*."
                f"\nJob ID: `{job.job_id}`"
                f"\nPoll status: `/sre access sync status {job.job_id}`"
            ),
            user_email=user_email,
            platform=platform,
            job_id=job.job_id,
        ),
        ephemeral=False,
    )


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

    result = enqueue_platform_sync(
        coordinator=coordinator,
        idempotency=idempotency,
        settings=settings,
        platform=platform,
        dry_run=dry_run,
    )

    if not result.is_success or result.data is None:
        if result.error_code == "FEATURE_DISABLED":
            log.warning("access_sync_disabled_rejected")
            return CommandResponse(
                message=t(
                    "access_sync.disabled",
                    locale,
                    "\u26d4 Access Sync is not enabled. Contact your administrator.",
                ),
                ephemeral=True,
            )
        return CommandResponse(
            message=t(
                "access_sync.platform.result.error",
                locale,
                f"\u274c Unexpected error: {result.message}",
            ),
            ephemeral=True,
        )

    job = result.data
    if job.already_running:
        log.info("platform_sync_already_running", existing_job_id=job.job_id)
        return CommandResponse(
            message=t(
                "access_sync.platform.result.already_running",
                locale,
                (
                    f"\u23f3 Platform sync already in progress for *{platform}*."
                    f"\nJob ID: `{job.job_id}`"
                    f"\nPoll status: `/sre access sync status {job.job_id}`"
                ),
                platform=platform,
                job_id=job.job_id,
            ),
            ephemeral=True,
        )

    log.info("platform_sync_job_enqueued", job_id=job.job_id)
    return CommandResponse(
        message=t(
            "access_sync.platform.result.enqueued",
            locale,
            (
                f"\u2705 Platform sync job enqueued for *{platform}*.\n"
                f"Job ID: `{job.job_id}`\n"
                f"Poll status: `/sre access sync status {job.job_id}`"
            ),
            platform=platform,
            job_id=job.job_id,
        ),
        ephemeral=False,
    )


def handle_sync_status_command(
    payload: CommandPayload,
    parsed_args: Dict[str, Any],
) -> CommandResponse:
    """Handle /sre access sync status <job_id>.

    Reads the job record from the idempotency store and returns a formatted
    status message using the shared presenter.
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
                f"\u26a0\ufe0f No sync job found with ID: `{job_id}`",
                job_id=job_id,
            ),
            ephemeral=True,
        )

    message = to_slack_status_message(SyncJobStatusResponse(**record), locale)
    return CommandResponse(message=message, ephemeral=True)
