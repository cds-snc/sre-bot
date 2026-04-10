"""Slack platform integration for Access Sync.

Registers the /sre access-sync Slack command and its subcommands.

NOTE: This is a v1 skeleton.  The command surface is intentionally
minimal — full interactive operator workflows (reconciliation triggers,
dry-run previews, status dashboards) are planned for a future release.
"""

from typing import Any, Dict, TYPE_CHECKING

import structlog

from infrastructure.operations import OperationStatus
from infrastructure.platforms.models import CommandPayload, CommandResponse
from infrastructure.platforms.parsing import Argument, ArgumentType
from packages.access.sync.providers import (
    get_access_sync_adapters,
    get_access_sync_coordinator,
)

if TYPE_CHECKING:
    from infrastructure.platforms.providers.slack import SlackPlatformProvider

logger = structlog.get_logger()


def register_commands(provider: "SlackPlatformProvider") -> None:
    """Register access-sync Slack commands with the provider."""
    provider.register_command(
        command="access-sync",
        parent="sre",
        handler=handle_sync_command,
        description="Trigger an on-demand access sync for a user on a platform",
        description_key="access_sync.description",
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
                name="dry_run",
                type=ArgumentType.BOOLEAN,
                required=False,
                description="Preview planned actions without executing",
            ),
        ],
    )

    provider.register_command(
        command="access-sync-status",
        parent="sre",
        handler=handle_status_command,
        description="Show registered access-sync platform adapters",
        description_key="access_sync.status.description",
        usage_hint="",
        examples=[],
        example_keys=[],
        arguments=[],
    )


def handle_sync_command(
    payload: CommandPayload,
    parsed_args: Dict[str, Any],
) -> CommandResponse:
    """Handle /sre access-sync <user_email> <platform> [--dry-run]."""
    log = logger.bind(
        command="access-sync",
        user_id=payload.user_id,
        channel_id=payload.channel_id,
    )
    log.info("slack_command_received", text=payload.text)

    user_email = str(parsed_args.get("user_email", "")).strip().lower()
    platform = str(parsed_args.get("platform", "")).strip().lower()
    dry_run = bool(parsed_args.get("dry_run", False))

    coordinator = get_access_sync_coordinator()
    result = coordinator.sync_user(
        user_email=user_email,
        platform=platform,
        dry_run=dry_run,
        request_id=(
            payload.correlation_id if hasattr(payload, "correlation_id") else ""
        ),
    )

    if result.is_success:
        outcome = result.data
        applied_actions = outcome.applied_actions if outcome else []
        prefix = (
            "Dry-run — planned actions"
            if dry_run
            else "Sync complete — actions applied"
        )
        actions_text = (
            "\n".join(f"• `{a}`" for a in applied_actions)
            if applied_actions
            else "_(none)_"
        )
        manual_note = (
            "\n⚠️ Some actions require manual follow-up."
            if outcome and outcome.requires_manual_action
            else ""
        )
        return CommandResponse(
            message=(
                f"{prefix} for *{user_email}* on *{platform}*:"
                f"\n{actions_text}{manual_note}"
            ),
            ephemeral=False,
        )

    if result.status == OperationStatus.NOT_FOUND:
        return CommandResponse(
            message=f"⚠️ Not found: {result.message}",
            ephemeral=True,
        )

    return CommandResponse(
        message=f"❌ Sync failed: {result.message}",
        ephemeral=True,
    )


def handle_status_command(payload: CommandPayload) -> CommandResponse:
    """Handle /sre access-sync-status."""
    platforms = sorted(get_access_sync_adapters().keys())
    if platforms:
        platform_list = ", ".join(f"`{p}`" for p in platforms)
        text = f"Access Sync — registered platforms: {platform_list}"
    else:
        text = "Access Sync — no platforms registered (check ACCESS_CONFIG_SOURCE)."
    return CommandResponse(message=text, ephemeral=True)
