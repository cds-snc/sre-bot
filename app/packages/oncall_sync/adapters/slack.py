"""Slack adapter — implements ``UserGroupSyncTarget``.

Resolves on-call user emails to Slack user IDs, finds (or creates) the
matching user group, re-enables it if it was deleted, then updates membership:

- Rotation groups are set to exactly one user (the current on-call person).
- Schedule aggregate groups are set to all currently on-call users across the
  schedule's rotations.
"""

from __future__ import annotations

from collections.abc import Sequence

import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from packages.oncall_sync.ports import OnCallSyncError
from packages.oncall_sync.settings import OnCallRotation, OnCallScheduleConfig

logger = structlog.get_logger()


class SlackUserGroupTarget:
    """Mirror on-call membership into Slack user groups."""

    def __init__(self, client: WebClient) -> None:
        self._client = client

    def sync_user_group(
        self,
        rotation: OnCallRotation,
        on_call_email: str,
    ) -> None:
        """Set the rotation user group to the single on-call user."""
        log = logger.bind(
            slack_handle=rotation.slack_handle,
            opsgenie_schedule_id=rotation.opsgenie_schedule_id,
            opsgenie_rotation_name=rotation.opsgenie_rotation_name,
        )

        user_id = self._resolve_user_id(on_call_email, log)
        if user_id is None:
            # Email did not resolve to a Slack user (the on-call user's
            # OpsGenie email differs from their Slack email). Already
            # logged; skip this rotation rather than emptying the group.
            return

        try:
            usergroup_id = self._find_or_create_usergroup(
                rotation.slack_handle, rotation.slack_name, rotation.slack_description, log
            )
            self._client.usergroups_users_update(usergroup=usergroup_id, users=user_id)
        except SlackApiError as exc:
            raise OnCallSyncError(f"Slack API call failed: {exc.response.get('error')}") from exc

        log.info("oncall_sync_usergroup_updated", usergroup_id=usergroup_id)

    def sync_schedule_user_group(
        self,
        schedule: OnCallScheduleConfig,
        on_call_emails: Sequence[str],
    ) -> None:
        """Set the schedule aggregate user group to all currently on-call users."""
        log = logger.bind(slack_handle=schedule.slack_handle)

        user_ids = [
            uid
            for email in on_call_emails
            if (uid := self._resolve_user_id(email, log)) is not None
        ]
        if not user_ids:
            log.info("oncall_sync_schedule_group_no_resolvable_users")
            return

        try:
            usergroup_id = self._find_or_create_usergroup(
                schedule.slack_handle, schedule.slack_name, schedule.slack_description, log
            )
            self._client.usergroups_users_update(
                usergroup=usergroup_id, users=",".join(user_ids)
            )
        except SlackApiError as exc:
            raise OnCallSyncError(f"Slack API call failed: {exc.response.get('error')}") from exc

        log.info("oncall_sync_schedule_usergroup_updated", usergroup_id=usergroup_id)

    def _resolve_user_id(self, email: str, log) -> str | None:
        try:
            resp = self._client.users_lookupByEmail(email=email)
        except SlackApiError as exc:
            log.error(
                "oncall_sync_user_lookup_failed",
                email=email,
                error=exc.response.get("error"),
            )
            return None
        if resp.get("ok"):
            user_id: str = resp["user"]["id"]
            return user_id
        return None

    def _find_or_create_usergroup(
        self, handle: str, name: str, description: str, log
    ) -> str:
        existing = self._lookup_usergroup(handle)
        if existing is not None:
            group_id, is_disabled = existing
            if is_disabled:
                self._client.usergroups_enable(usergroup=group_id)
            return group_id

        created = self._client.usergroups_create(
            name=name,
            handle=handle,
            description=description,
        )
        usergroup_id: str = created["usergroup"]["id"]
        log.info("oncall_sync_usergroup_created", usergroup_id=usergroup_id)
        return usergroup_id

    def _lookup_usergroup(self, handle: str) -> tuple[str, bool] | None:
        response = self._client.usergroups_list(include_disabled=True)
        usergroups: list[dict] = response.get("usergroups", []) or []
        for group in usergroups:
            if group.get("handle") == handle:
                return group["id"], bool(group.get("date_delete", 0))
        return None
