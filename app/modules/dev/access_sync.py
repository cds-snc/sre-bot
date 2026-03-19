"""Dev smoke command for Access Sync.

Provides a minimal development command surface to exercise the current
Access Sync implementation end-to-end for a single user and platform.

Usage:
    /sre dev access-sync <user_email> <platform> [--dry-run]

Examples:
    /sre dev access-sync user@example.com aws
    /sre dev access-sync user@example.com aws --dry-run
"""

from typing import Any, Callable

import structlog

from infrastructure.operations import OperationStatus
from infrastructure.platforms.models import CommandPayload
from infrastructure.platforms.parsing import (
    Argument,
    ArgumentParsingError,
    ArgumentType,
    CommandArgumentParser,
)
from packages.access_sync.providers import (
    get_access_sync_registry,
    get_access_sync_runtime_config,
    get_access_sync_service,
)

logger = structlog.get_logger()

_ACCESS_SYNC_ARGUMENT_PARSER = CommandArgumentParser(
    [
        Argument(name="user_email", type=ArgumentType.EMAIL, required=True),
        Argument(name="platform", type=ArgumentType.STRING, required=True),
        Argument(
            name="--dry-run",
            type=ArgumentType.BOOLEAN,
            required=False,
            default=False,
        ),
    ]
)

_ACCESS_SYNC_RECONCILE_ARGUMENT_PARSER = CommandArgumentParser(
    [
        Argument(name="platform", type=ArgumentType.STRING, required=False),
        Argument(
            name="--dry-run",
            type=ArgumentType.BOOLEAN,
            required=False,
            default=False,
        ),
    ]
)


def _parse_access_sync_inputs(
    command_payload: CommandPayload | None,
) -> tuple[str, str, bool]:
    """Parse user_email, platform, and dry-run flag from command text."""
    raw_text = command_payload.text if command_payload is not None else ""
    parsed = _ACCESS_SYNC_ARGUMENT_PARSER.parse(raw_text)

    user_email = str(parsed["user_email"]).strip().lower()
    platform = str(parsed["platform"]).strip().lower()
    dry_run = bool(parsed.get("--dry-run", False))
    return user_email, platform, dry_run


def _parse_access_sync_reconcile_inputs(
    command_payload: CommandPayload | None,
) -> tuple[str, bool]:
    """Parse optional platform and dry-run flag for reconcile placeholder."""
    raw_text = command_payload.text if command_payload is not None else ""
    parsed = _ACCESS_SYNC_RECONCILE_ARGUMENT_PARSER.parse(raw_text)

    platform = str(parsed.get("platform", "")).strip().lower()
    dry_run = bool(parsed.get("--dry-run", False))
    return platform, dry_run


def access_sync_command(
    ack: Callable[[], None],
    client: Any,
    body: dict[str, Any],
    respond: Callable[..., None],
    command_payload: CommandPayload | None = None,
) -> None:
    """Handle /sre dev access-sync command.

    This intentionally exposes a single feature path for development testing:
    invoke AccessSyncService.sync_user with parsed command inputs.
    """
    ack()

    try:
        user_email, platform, dry_run = _parse_access_sync_inputs(command_payload)
    except ArgumentParsingError as exc:
        respond(
            "Usage: /sre dev access-sync <user_email> <platform> [--dry-run]\n"
            f"Argument parsing error: {exc.message}"
        )
        return

    correlation_id = (
        command_payload.correlation_id if command_payload is not None else ""
    )

    log = logger.bind(
        command="dev_access_sync",
        user_email=user_email,
        platform=platform,
        dry_run=dry_run,
        correlation_id=correlation_id,
    )
    log.info("dev_access_sync_started")

    result = get_access_sync_service().sync_user(
        user_email=user_email,
        platform=platform,
        dry_run=dry_run,
        request_id=correlation_id,
    )

    if result.is_success:
        actions = result.data if result.data is not None else []
        actions_text = "\n".join(f"- {action}" for action in actions)
        if not actions_text:
            actions_text = "- (none)"

        mode_text = "Dry-run planned actions" if dry_run else "Applied actions"
        respond(
            "✅ Access Sync command completed\n"
            f"user: {user_email}\n"
            f"platform: {platform}\n"
            f"status: {result.message}\n"
            f"{mode_text}:\n{actions_text}"
        )
        log.info("dev_access_sync_completed", action_count=len(actions))
        return

    if result.status == OperationStatus.NOT_FOUND:
        respond(f"⚠️ Access Sync not found error: {result.message}")
    elif result.status == OperationStatus.PERMANENT_ERROR:
        respond(f"❌ Access Sync validation/policy error: {result.message}")
    else:
        respond(f"❌ Access Sync execution failed: {result.message}")

    log.warning(
        "dev_access_sync_failed",
        status=str(result.status),
        error_code=result.error_code,
        message=result.message,
    )


def access_sync_reconcile_command(
    ack: Callable[[], None],
    client: Any,
    body: dict[str, Any],
    respond: Callable[..., None],
    command_payload: CommandPayload | None = None,
) -> None:
    """Handle /sre dev access-sync-reconcile placeholder command.

    This is intentionally a placeholder until the reconciliation engine is
    implemented. It reports currently configured policy and adapter platforms
    so operators can validate runtime wiring.
    """
    ack()

    try:
        platform, dry_run = _parse_access_sync_reconcile_inputs(command_payload)
    except ArgumentParsingError as exc:
        respond(
            "Usage: /sre dev access-sync-reconcile [platform] [--dry-run]\n"
            f"Argument parsing error: {exc.message}"
        )
        return

    correlation_id = (
        command_payload.correlation_id if command_payload is not None else ""
    )
    log = logger.bind(
        command="dev_access_sync_reconcile",
        platform=platform,
        dry_run=dry_run,
        correlation_id=correlation_id,
    )
    log.info("dev_access_sync_reconcile_placeholder_called")

    runtime_config = get_access_sync_runtime_config()
    policy_platforms = sorted(runtime_config.policies.keys())
    adapter_platforms = get_access_sync_registry().registered_platforms()

    requested_platform = platform if platform else "(not specified)"
    policy_text = ", ".join(policy_platforms) if policy_platforms else "(none)"
    adapter_text = ", ".join(adapter_platforms) if adapter_platforms else "(none)"

    if platform and platform not in runtime_config.policies:
        platform_note = f"Requested platform '{platform}' is not configured in policy."
    else:
        platform_note = "Requested platform is present in policy (or not provided)."

    respond(
        "⚠️ Access Sync reconciliation placeholder\n"
        "Status: not implemented yet (service-level scheduled reconciliation pending)\n"
        f"requested_platform: {requested_platform}\n"
        f"dry_run_flag: {dry_run}\n"
        f"policy_platforms: {policy_text}\n"
        f"adapter_platforms: {adapter_text}\n"
        f"note: {platform_note}"
    )
