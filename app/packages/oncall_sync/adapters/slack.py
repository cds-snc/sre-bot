"""Slack adapter — implements ``UserGroupSyncTarget``.

Resolves the on-call user's Slack user ID by email, finds (or creates) the
user group identified by ``rotation.slack_handle``, re-enables it if it was
deleted, then sets its membership to the single on-call user.
"""

from __future__ import annotations

import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from packages.oncall_sync.ports import OnCallSyncError
from packages.oncall_sync.settings import OnCallRotation

logger = structlog.get_logger()


class SlackUserGroupTarget:
    """Mirror the current on-call user into a Slack user group."""

    def __init__(self, client: WebClient) -> None:
        self._client = client

    def sync_user_group(
        self,
        rotation: OnCallRotation,
        on_call_email: str,
    ) -> None:
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
            usergroup_id = self._find_or_create_usergroup(rotation, log)
            self._client.usergroups_users_update(usergroup=usergroup_id, users=user_id)
        except SlackApiError as exc:
            raise OnCallSyncError(
                f"Slack API call failed: {exc.response.get('error')}"
            ) from exc

        log.info("oncall_sync_usergroup_updated", usergroup_id=usergroup_id)

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

    def _find_or_create_usergroup(self, rotation: OnCallRotation, log) -> str:
        existing = self._lookup_usergroup(rotation.slack_handle)
        if existing is not None:
            group_id, is_disabled = existing
            if is_disabled:
                self._client.usergroups_enable(usergroup=group_id)
            return group_id

        created = self._client.usergroups_create(
            name=rotation.slack_name,
            handle=rotation.slack_handle,
            description=rotation.slack_description,
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
