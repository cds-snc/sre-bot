"""Slack adapter — implements ``UserGroupSyncTarget``.

Resolves on-call user emails to Slack user IDs, finds (or creates) the
matching user group, re-enables it if it was deleted, then sets its membership
to exactly the provided users. Used for both single-user rotation groups and
multi-user schedule aggregate groups.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from packages.oncall_sync.ports import OnCallSyncError

logger = structlog.get_logger()


def _fingerprint_email(email: str) -> str:
    """Privacy-safe, stable identifier for correlating repeated mismatches."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


class SlackUserGroupTarget:
    """Mirror on-call membership into Slack user groups."""

    def __init__(self, client: WebClient, *, approved_domains: frozenset[str] = frozenset()) -> None:
        self._client = client
        self._approved_domains = approved_domains

    def sync_user_group(
        self,
        handle: str,
        name: str,
        description: str,
        emails: Sequence[str],
    ) -> None:
        """Set the user group to contain exactly the resolved on-call users."""
        log = logger.bind(slack_handle=handle)

        user_ids = [uid for email in emails if (uid := self._resolve_user_id(email, log)) is not None]
        if not user_ids:
            # No emails resolved to Slack users — skip rather than empty the group.
            log.info("oncall_sync_usergroup_no_resolvable_users")
            return

        try:
            usergroup_id = self._find_or_create_usergroup(handle, name, description, log)
            self._client.usergroups_users_update(usergroup=usergroup_id, users=",".join(user_ids))
        except SlackApiError as exc:
            raise OnCallSyncError(f"Slack API call failed: {exc.response.get('error')}") from exc

        log.info("oncall_sync_usergroup_updated", usergroup_id=usergroup_id)

    def _resolve_user_id(self, email: str, log) -> str | None:
        if self._approved_domains and not self._is_approved_domain(email):
            log.info(
                "oncall_sync_participant_email_domain_mismatch",
                email_fingerprint=_fingerprint_email(email),
            )
            return None
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

    def _is_approved_domain(self, email: str) -> bool:
        domain = email.rsplit("@", 1)[-1].strip().lower() if "@" in email else ""
        return domain in self._approved_domains

    def _find_or_create_usergroup(self, handle: str, name: str, description: str, log) -> str:
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
