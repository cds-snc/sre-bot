"""Sync OpsGenie rotation on-call user into a Slack user group.

Each configured rotation has exactly one user on-call at a time. When the
rotation has no current on-call (a gap in coverage), the matching Slack
user group is left unchanged so it never sits empty.

The sync is designed to be naturally idempotent to be compatible with HA.
"""

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from structlog import get_logger

from infrastructure.configuration.features.slack_opsgenie_sync import (
    OnCallRotation,
    get_slack_opsgenie_sync_settings,
)
from integrations.opsgenie import OpsGenieAPIError, get_on_call_user_for_rotation
from integrations.slack.client import SlackClientManager

logger = get_logger()


class RotationSyncError(Exception):
    """Raised when a single rotation fails to sync."""


def sync_all_rotations() -> None:
    """Sync every configured rotation. Per-rotation failures are isolated."""
    settings = get_slack_opsgenie_sync_settings()
    client = SlackClientManager.get_client()
    for rotation in settings.rotations:
        try:
            _sync_rotation(client, rotation)
        except RotationSyncError as exc:
            cause = exc.__cause__
            logger.error(
                "slack_opsgenie_sync_rotation_failed",
                slack_handle=rotation.slack_handle,
                opsgenie_schedule_id=rotation.opsgenie_schedule_id,
                opsgenie_rotation_name=rotation.opsgenie_rotation_name,
                error=str(exc),
                error_type=type(cause).__name__ if cause is not None else None,
            )


def _sync_rotation(client: WebClient, rotation: OnCallRotation) -> None:
    log = logger.bind(
        slack_handle=rotation.slack_handle,
        opsgenie_schedule_id=rotation.opsgenie_schedule_id,
        opsgenie_rotation_name=rotation.opsgenie_rotation_name,
    )

    try:
        email = get_on_call_user_for_rotation(
            rotation.opsgenie_schedule_id, rotation.opsgenie_rotation_name
        )
    except OpsGenieAPIError as exc:
        raise RotationSyncError(str(exc)) from exc

    if email is None:
        log.info("slack_opsgenie_sync_rotation_empty")
        return

    try:
        user_id = _resolve_user_id(client, email, log)
        if user_id is None:
            # Email did not resolve to a Slack user (OpsGenie email differs
            # from the user's Slack email). Logged as an error in
            # _resolve_user_id; skip this rotation for now.
            return

        usergroup_id = _find_or_create_usergroup(client, rotation, log)
        client.usergroups_users_update(usergroup=usergroup_id, users=user_id)
    except SlackApiError as exc:
        raise RotationSyncError(
            f"Slack API call failed: {exc.response.get('error')}"
        ) from exc

    log.info(
        "slack_opsgenie_sync_rotation_synced",
        usergroup_id=usergroup_id,
    )


def _resolve_user_id(client: WebClient, email: str, log) -> str | None:
    try:
        resp = client.users_lookupByEmail(email=email)
    except SlackApiError as exc:
        log.error(
            "slack_opsgenie_sync_user_lookup_failed",
            email=email,
            error=exc.response.get("error"),
        )
        return None
    if resp.get("ok"):
        return resp["user"]["id"]
    return None


def _find_or_create_usergroup(client: WebClient, rotation: OnCallRotation, log) -> str:
    existing = _lookup_usergroup(client, rotation.slack_handle)
    if existing is not None:
        group_id, is_disabled = existing
        if is_disabled:
            client.usergroups_enable(usergroup=group_id)
        return group_id

    created = client.usergroups_create(
        name=rotation.slack_name,
        handle=rotation.slack_handle,
        description=rotation.slack_description,
    )
    usergroup_id: str = created["usergroup"]["id"]
    log.info("slack_opsgenie_sync_usergroup_created", usergroup_id=usergroup_id)
    return usergroup_id


def _lookup_usergroup(client: WebClient, handle: str) -> tuple[str, bool] | None:
    response = client.usergroups_list(include_disabled=True)
    usergroups: list[dict] = response.get("usergroups", []) or []
    for group in usergroups:
        if group.get("handle") == handle:
            return group["id"], bool(group.get("date_delete", 0))
    return None
