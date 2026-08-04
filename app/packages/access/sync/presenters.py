"""Sync job status presenters.

Maps internal job record dicts (read from the idempotency store) to
transport-appropriate response shapes. All status formatting logic lives
here so HTTP routes and Slack handlers share a single source of truth.
"""

from typing import Any

from infrastructure.i18n import t
from packages.access.sync.job_models import JobStatus
from packages.access.sync.schemas import SyncJobStatusResponse

_MAX_LIFECYCLE_USERS = 8
_MAX_ENTITLEMENTS = 8
_MAX_USERS_PER_ENTITLEMENT = 3
_MAX_USER_ACTIONS = 6


def to_http_status_response(record: dict[str, Any]) -> SyncJobStatusResponse:
    """Convert a stored job record dict to an HTTP polling response model."""
    return SyncJobStatusResponse(**record)


def to_slack_status_message(record: SyncJobStatusResponse, locale: str) -> str:
    """Format a stored job record as a localized Slack status message."""
    status = record.status
    job_id = record.job_id
    platform = record.platform
    started_at = record.started_at or ""

    if status == JobStatus.IN_PROGRESS:
        return str(
            t(
                "access_sync.status.result.running",
                locale,
                f"\u23f3 Sync job `{job_id}` is *in progress* for platform *{platform}*.\nStarted: {started_at}",
                job_id=job_id,
                platform=platform,
                started_at=started_at,
            )
        )

    if status == JobStatus.COMPLETED:
        sync_type = record.sync_type or ""
        completed_at = record.completed_at or ""

        if sync_type == "user":
            user_email = record.user_email or ""
            actions_planned = record.actions_planned or []
            actions_applied = record.actions_applied or []
            requires_manual = record.requires_manual_action or False
            user_sections: list[str] = [
                str(
                    t(
                        "access_sync.status.result.completed_user_header",
                        locale,
                        f"\u2705 User sync `{job_id}` *completed* for *{user_email}* on *{platform}*.",
                        job_id=job_id,
                        user_email=user_email,
                        platform=platform,
                    )
                ),
                str(
                    t(
                        "access_sync.status.result.completed_user_counts",
                        locale,
                        (f"Actions planned: {len(actions_planned)} | Applied: {len(actions_applied)}"),
                        actions_planned_count=len(actions_planned),
                        actions_applied_count=len(actions_applied),
                    )
                ),
            ]

            if actions_planned:
                user_sections.append(
                    str(
                        t(
                            "access_sync.status.result.completed_user_planned_actions",
                            locale,
                            (f"Planned actions: {_truncate_list(actions_planned, _MAX_USER_ACTIONS)}"),
                            actions=_truncate_list(actions_planned, _MAX_USER_ACTIONS),
                        )
                    )
                )
            if actions_applied:
                user_sections.append(
                    str(
                        t(
                            "access_sync.status.result.completed_user_applied_actions",
                            locale,
                            (f"Applied actions: {_truncate_list(actions_applied, _MAX_USER_ACTIONS)}"),
                            actions=_truncate_list(actions_applied, _MAX_USER_ACTIONS),
                        )
                    )
                )
            if requires_manual:
                user_sections.append(
                    str(
                        t(
                            "access_sync.status.result.completed_user_manual",
                            locale,
                            "\u26a0\ufe0f Manual action required",
                        )
                    )
                )

            user_sections.append(
                str(
                    t(
                        "access_sync.status.result.completed_timestamp",
                        locale,
                        f"Completed: {completed_at}",
                        completed_at=completed_at,
                    )
                )
            )
            return "\n".join(line for line in user_sections if line)

        users_synced = record.users_synced or 0
        users_converged = record.users_converged or 0
        orphans_found = record.orphans_found or 0
        requires_manual_count = record.requires_manual_action_count or 0
        changed_user_count = record.changed_user_count or users_converged
        unchanged_user_count = record.unchanged_user_count or max(
            users_synced - changed_user_count,
            0,
        )
        action_counts = record.action_counts or {}
        lifecycle_actions = record.lifecycle_actions or {}
        entitlements_by_action = record.entitlements_by_action or {}

        sections: list[str] = [
            str(
                t(
                    "access_sync.status.result.completed_header",
                    locale,
                    f"\u2705 Sync job `{job_id}` *completed* for platform *{platform}*.",
                    job_id=job_id,
                    platform=platform,
                )
            ),
            str(
                t(
                    "access_sync.status.result.completed_summary",
                    locale,
                    f"Users synced: {users_synced} | Changed: {changed_user_count} | Unchanged: {unchanged_user_count}",
                    users_synced=users_synced,
                    changed_user_count=changed_user_count,
                    unchanged_user_count=unchanged_user_count,
                )
            ),
            str(
                t(
                    "access_sync.status.result.completed_lifecycle",
                    locale,
                    (
                        f"Lifecycle: +{action_counts.get('provision_user', 0)} provision | "
                        f"-{action_counts.get('remove_user', 0)} remove | "
                        f"{action_counts.get('disable_user', 0)} disable"
                    ),
                    provision_count=action_counts.get("provision_user", 0),
                    remove_count=action_counts.get("remove_user", 0),
                    disable_count=action_counts.get("disable_user", 0),
                )
            ),
            str(
                t(
                    "access_sync.status.result.completed_entitlements",
                    locale,
                    (
                        f"Entitlements: +{action_counts.get('apply_entitlement', 0)} apply | "
                        f"-{action_counts.get('remove_entitlement', 0)} remove"
                    ),
                    apply_count=action_counts.get("apply_entitlement", 0),
                    remove_count=action_counts.get("remove_entitlement", 0),
                )
            ),
            str(
                t(
                    "access_sync.status.result.completed_risk",
                    locale,
                    f"Orphans: {orphans_found} | Manual actions: {requires_manual_count}",
                    orphans_found=orphans_found,
                    requires_manual_action_count=requires_manual_count,
                )
            ),
        ]
        sections.extend(_format_lifecycle_details(lifecycle_actions, locale))
        sections.extend(_format_entitlement_details(entitlements_by_action, locale))
        sections.append(
            str(
                t(
                    "access_sync.status.result.completed_timestamp",
                    locale,
                    f"Completed: {completed_at}",
                    completed_at=completed_at,
                )
            )
        )
        return "\n".join(line for line in sections if line)

    if status == JobStatus.FAILED:
        error = record.error or "Unknown error"
        return str(
            t(
                "access_sync.status.result.failed",
                locale,
                f"\u274c Sync job `{job_id}` *failed* for platform *{platform}*.\nError: {error}",
                job_id=job_id,
                platform=platform,
                error=error,
            )
        )

    return str(
        t(
            "access_sync.status.result.unknown",
            locale,
            f"\u2753 Sync job `{job_id}` has unknown status: *{status}*",
            job_id=job_id,
            status=status,
        )
    )


def _format_lifecycle_details(
    lifecycle_actions: dict[str, Any],
    locale: str,
) -> list[str]:
    """Return a concise lifecycle preview block for Slack status messages."""
    provision_users = [str(user) for user in lifecycle_actions.get("provision_user", []) if user]
    remove_users = [str(user) for user in lifecycle_actions.get("remove_user", []) if user]
    disable_users = [str(user) for user in lifecycle_actions.get("disable_user", []) if user]

    details: list[str] = []
    if provision_users:
        details.append(
            str(
                t(
                    "access_sync.status.result.completed_lifecycle_provision",
                    locale,
                    (f"• Users to provision ({len(provision_users)}): {_truncate_list(provision_users, _MAX_LIFECYCLE_USERS)}"),
                    count=len(provision_users),
                    users=_truncate_list(provision_users, _MAX_LIFECYCLE_USERS),
                )
            )
        )
    if remove_users:
        details.append(
            str(
                t(
                    "access_sync.status.result.completed_lifecycle_remove",
                    locale,
                    (f"• Users to remove ({len(remove_users)}): {_truncate_list(remove_users, _MAX_LIFECYCLE_USERS)}"),
                    count=len(remove_users),
                    users=_truncate_list(remove_users, _MAX_LIFECYCLE_USERS),
                )
            )
        )
    if disable_users:
        details.append(
            str(
                t(
                    "access_sync.status.result.completed_lifecycle_disable",
                    locale,
                    (f"• Users to disable ({len(disable_users)}): {_truncate_list(disable_users, _MAX_LIFECYCLE_USERS)}"),
                    count=len(disable_users),
                    users=_truncate_list(disable_users, _MAX_LIFECYCLE_USERS),
                )
            )
        )
    return details


def _format_entitlement_details(
    entitlements_by_action: dict[str, Any],
    locale: str,
) -> list[str]:
    """Return a concise entitlement preview block for Slack status messages."""
    details: list[str] = []
    details.extend(
        _format_entitlement_action_details(
            action_key="access_sync.status.result.completed_entitlement_add",
            fallback_prefix="• Entitlement adds",
            mapping=entitlements_by_action.get("apply_entitlement", {}),
            locale=locale,
        )
    )
    details.extend(
        _format_entitlement_action_details(
            action_key="access_sync.status.result.completed_entitlement_remove",
            fallback_prefix="• Entitlement removals",
            mapping=entitlements_by_action.get("remove_entitlement", {}),
            locale=locale,
        )
    )
    return details


def _format_entitlement_action_details(
    action_key: str,
    fallback_prefix: str,
    mapping: Any,
    locale: str,
) -> list[str]:
    """Format one entitlement action block with truncation for readability."""
    if not isinstance(mapping, dict) or not mapping:
        return []

    entries: list[tuple[str, list[str]]] = []
    for slug, users in sorted(mapping.items()):
        if not isinstance(slug, str):
            continue
        normalized_users = [str(user) for user in users] if isinstance(users, list) else []
        entries.append((slug, normalized_users))

    lines: list[str] = []
    for slug, users in entries[:_MAX_ENTITLEMENTS]:
        lines.append(
            str(
                t(
                    action_key,
                    locale,
                    (f"{fallback_prefix} — *{slug}* ({len(users)}): {_truncate_list(users, _MAX_USERS_PER_ENTITLEMENT)}"),
                    slug=slug,
                    count=len(users),
                    users=_truncate_list(users, _MAX_USERS_PER_ENTITLEMENT),
                )
            )
        )

    hidden = len(entries) - _MAX_ENTITLEMENTS
    if hidden > 0:
        lines.append(
            str(
                t(
                    "access_sync.status.result.completed_entitlement_more",
                    locale,
                    f"• ... and {hidden} more entitlement groups",
                    count=hidden,
                )
            )
        )
    return lines


def _truncate_list(items: list[str], max_items: int) -> str:
    """Return a comma-delimited list truncated with an overflow suffix."""
    visible = items[:max_items]
    hidden = len(items) - len(visible)
    base = ", ".join(visible)
    if hidden > 0:
        return f"{base} (+{hidden} more)"
    return base
