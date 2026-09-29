"""Slack adapter — implements ``UserGroupSyncTarget``.

Resolves on-call user emails to Slack user IDs, finds (or creates) the
matching user group, re-enables it if it was deleted, then sets its membership
to exactly the provided users. Used for both single-user rotation groups and
multi-user schedule aggregate groups.
"""

import hashlib
from collections.abc import Sequence

import structlog
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from contracts.operations.status import OperationStatus
from integrations.slack.client import classify_slack_error, get_slack_web_client
from integrations.slack.settings import get_slack_settings
from packages.oncall_sync.ports import OnCallSyncError

logger = structlog.get_logger()


def _fingerprint_email(email: str) -> str:
    """Privacy-safe, stable identifier for correlating repeated mismatches."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _classify(exc: SlackApiError) -> tuple[OperationStatus | None, str | None]:
    """Classified status and error code, or no status for a code the catalogues do not name.

    Unnamed codes are still Slack failures of this one group, so they stay
    ``OnCallSyncError``s and the service keeps syncing the other groups.
    """
    try:
        status, error_code, _ = classify_slack_error(exc)
    except SlackApiError:
        return None, exc.response.get("error")
    return status, error_code


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

        self.sync_user_group_ids(handle, name, description, user_ids)

    def sync_user_group_ids(
        self,
        handle: str,
        name: str,
        description: str,
        user_ids: Sequence[str],
    ) -> None:
        """Set the user group to contain exactly the supplied Slack user IDs."""
        log = logger.bind(slack_handle=handle)
        try:
            usergroup_id = self._find_or_create_usergroup(handle, name, description, log)
            self._client.usergroups_users_update(usergroup=usergroup_id, users=",".join(user_ids))
        except SlackApiError as exc:
            status, error_code = _classify(exc)
            detail = error_code if status is None else f"{error_code} ({status.value})"
            raise OnCallSyncError(f"Slack API call failed: {detail}") from exc
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
            status, error_code = _classify(exc)
            log.error(
                "oncall_sync_user_lookup_failed",
                email=email,
                error=error_code,
                status=None if status is None else status.value,
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


def build_user_group_sync_target(*, approved_domains: frozenset[str] = frozenset()) -> SlackUserGroupTarget:
    """Build the target on the admin user token; ``usergroups.*`` writes reject the bot token."""
    if not get_slack_settings().USER_TOKEN:
        raise ValueError(
            "SLACK_USER_TOKEN is required to sync on-call rotations into Slack user groups "
            "(usergroups.* writes cannot use the shared inbound bot token)."
        )
    return SlackUserGroupTarget(get_slack_web_client(actor="user"), approved_domains=approved_domains)
