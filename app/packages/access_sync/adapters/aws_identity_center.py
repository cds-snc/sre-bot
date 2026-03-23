"""AWS Identity Center adapter - v1: group membership sync only.

Maps normalized Access Sync actions to AWS IdentityStore API calls.
All external API calls are wrapped in try/except and return OperationResult.
Clients are injected from infrastructure.services — never instantiated locally.

v1 entitlement model: entitlement_type="group"
    entitlement_id = AWS Identity Store GroupId (UUID)
    e.g. "a1b2c3d4-1234-5678-abcd-ef0123456789"

Group sync maps IDP security groups → AWS IC groups via group membership.
Direct user→account permission-set assignments are deferred to a future
"temporary elevated privileges" feature.

AWS IC has no native "disable" state at the identity-store level; disable_user
is therefore not supported and signals manual_action_required.
"""

import re
from typing import Any, Dict, List, Mapping, Optional, Set

import structlog

from infrastructure.clients.aws import AWSClients
from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.policies import AdapterCapabilities

logger = structlog.get_logger()


class AwsIdentityCenterAdapter:
    """AWS Identity Center adapter.

    Uses pre-configured centralized AWSClients to access IdentityStore and SsoAdmin.
    All external API calls wrapped in try/except, returning OperationResult.

    The AWSClients facade is received fully configured with AWS_SSO_INSTANCE_ID bootstrap
    setting applied to the underlying IdentityStoreClient. No additional configuration
    is needed at the feature layer—the client is ready to use.

    Args:
        aws_clients: Centralized AWS clients facade from infrastructure.services.
            Must have been initialized with AWS_SSO_INSTANCE_ID bootstrap setting.
    """

    def __init__(self, aws_clients: AWSClients) -> None:
        self._aws = aws_clients

    @staticmethod
    def _build_identitystore_name(user_email: str) -> Dict[str, str]:
        """Build a minimal AWS Identity Store Name payload from an email address."""
        local_part = user_email.split("@", 1)[0].strip()
        normalized = re.sub(r"[._-]+", " ", local_part)
        tokens = [token for token in normalized.split() if token]

        if not tokens:
            return {"GivenName": "User", "FamilyName": "Unknown"}
        if len(tokens) == 1:
            return {"GivenName": tokens[0].title(), "FamilyName": "User"}

        return {
            "GivenName": tokens[0].title(),
            "FamilyName": " ".join(token.title() for token in tokens[1:]),
        }

    def _extract_primary_email(self, user: Mapping[str, Any]) -> Optional[str]:
        """Return the primary email from an Identity Store user payload."""
        emails = user.get("Emails", [])
        if not isinstance(emails, list):
            return None

        for email_entry in emails:
            if not isinstance(email_entry, dict):
                continue
            value = email_entry.get("Value")
            if email_entry.get("Primary") and isinstance(value, str) and value:
                return value.strip().lower()
        return None

    def _list_users(self) -> OperationResult:
        """Return Identity Store users using the infrastructure client contract."""
        result = self._aws.identitystore.list_users()
        if not result.is_success:
            return result
        if not isinstance(result.data, list):
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Unexpected Identity Store list_users payload",
                error_code="INVALID_AWS_RESPONSE",
            )
        users: List[Mapping[str, Any]] = [
            item for item in result.data if isinstance(item, dict)
        ]
        return OperationResult.success(data=users)

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            supports_disable=False,  # AWS IC has no native identity-store disable
            supports_delete=True,
            supported_entitlement_types={"group"},  # v1: group membership sync only
        )

    def _find_user_id(self, user_email: str) -> OperationResult:
        """Resolve a user email to an Identity Store user ID.

        Returns SUCCESS with data={"user_id": str} or NOT_FOUND.
        Identity Store ID is obtained from the pre-configured client.
        """
        log = logger.bind(user_email=user_email, adapter="aws_identity_center")
        result = self._aws.identitystore.get_user_id_by_username(
            username=user_email,
        )
        if not result.is_success:
            # IdentityStore returns ResourceNotFoundException for unknown users.
            # Normalize that provider-specific error into NOT_FOUND so caller
            # logic (ensure_user idempotent create path) can proceed correctly.
            if result.error_code == "ResourceNotFoundException":
                return OperationResult.error(
                    OperationStatus.NOT_FOUND,
                    message=f"User not found in Identity Store: {user_email}",
                    error_code="USER_NOT_FOUND",
                )
            log.error("find_user_failed", error=result.message)
            return result

        data = result.data if isinstance(result.data, dict) else {}
        user_id = data.get("UserId")
        if not isinstance(user_id, str) or not user_id:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"User not found in Identity Store: {user_email}",
                error_code="USER_NOT_FOUND",
            )
        return OperationResult.success(data={"user_id": user_id})

    def get_user(self, user_email: str) -> OperationResult:
        """Look up a user; returns NOT_FOUND if missing."""
        return self._aws.identitystore.describe_user_by_username(username=user_email)

    def ensure_user(self, user_email: str) -> OperationResult:
        """Ensure the user exists in Identity Store; create if missing (idempotent)."""
        log = logger.bind(user_email=user_email, adapter="aws_identity_center")
        log.info("ensure_user_started")

        existing = self._find_user_id(user_email)
        if existing.is_success:
            log.info(
                "ensure_user_already_exists",
                user_id=(existing.data or {}).get("user_id"),
            )
            return existing

        if existing.status != OperationStatus.NOT_FOUND:
            return existing

        name = self._build_identitystore_name(user_email)
        display_name = f"{name['GivenName']} {name['FamilyName']}".strip()

        result = self._aws.identitystore.create_user(
            UserName=user_email,
            DisplayName=display_name,
            Name=name,
            Emails=[{"Value": user_email, "Primary": True, "Type": "WORK"}],
        )
        if result.is_success:
            user_id = (result.data or {}).get("UserId", "")
            log.info("ensure_user_created", user_id=user_id)
            return OperationResult.success(data={"user_id": user_id})

        log.error("ensure_user_failed", error=result.message)
        return result

    def disable_user(self, user_email: str) -> OperationResult:
        """Not natively supported in AWS Identity Store.

        AWS IC does not expose a disable/suspend state at the identity-store level.
        Returns PERMANENT_ERROR with error_code="UNSUPPORTED_OPERATION" so the
        service can flag the run as requiring manual action.
        """
        logger.bind(user_email=user_email, adapter="aws_identity_center").warning(
            "disable_user_not_supported"
        )
        return OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message=(
                f"AWS Identity Center does not support native disable. "
                f"Manual action required for user: {user_email}"
            ),
            error_code="UNSUPPORTED_OPERATION",
        )

    def remove_user(self, user_email: str) -> OperationResult:
        """Delete user from Identity Store (idempotent; no-op if already absent)."""
        log = logger.bind(user_email=user_email, adapter="aws_identity_center")
        log.info("remove_user_started")

        id_result = self._find_user_id(user_email)
        if not id_result.is_success:
            if id_result.status == OperationStatus.NOT_FOUND:
                log.info("remove_user_already_absent")
                return OperationResult.success(message="user_already_absent")
            return id_result

        user_id = (id_result.data or {}).get("user_id", "")
        result = self._aws.identitystore.delete_user(
            user_id=user_id,
        )
        if result.is_success:
            log.info("remove_user_deleted", user_id=user_id)
        else:
            log.error("remove_user_failed", user_id=user_id, error=result.message)
        return result

    def apply_entitlement(
        self,
        user_email: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        """Add a user to an AWS IC group (idempotent).

        v1: entitlement_type must be "group"; entitlement_id is the AWS IC GroupId.
        """
        log = logger.bind(
            user_email=user_email,
            entitlement_type=entitlement_type,
            entitlement_id=entitlement_id,
            adapter="aws_identity_center",
        )
        log.info("apply_entitlement_started")

        if entitlement_type != "group":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=(
                    f"Unsupported entitlement_type: {entitlement_type}. "
                    "v1 only supports 'group' (direct account assignments deferred)."
                ),
                error_code="UNSUPPORTED_ENTITLEMENT_TYPE",
            )

        id_result = self._find_user_id(user_email)
        if not id_result.is_success:
            return id_result
        user_id: str = (id_result.data or {}).get("user_id", "")

        # Check if already a member (idempotency).
        membership_result = self._aws.identitystore.get_group_membership_id(
            group_id=entitlement_id,
            member_id={"UserId": user_id},
        )
        if membership_result.is_success:
            log.info("apply_entitlement_already_member", group_id=entitlement_id)
            return OperationResult.success(message="group_membership_already_exists")
        if membership_result.status != OperationStatus.NOT_FOUND:
            return membership_result

        result = self._aws.identitystore.create_group_membership(
            GroupId=entitlement_id,
            MemberId={"UserId": user_id},
        )
        if result.is_success:
            log.info("apply_entitlement_added", group_id=entitlement_id)
        else:
            log.error("apply_entitlement_failed", error=result.message)
        return result

    def remove_entitlement(
        self,
        user_email: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        """Remove a user from an AWS IC group (idempotent).

        v1: entitlement_type must be "group"; entitlement_id is the AWS IC GroupId.
        """
        log = logger.bind(
            user_email=user_email,
            entitlement_type=entitlement_type,
            entitlement_id=entitlement_id,
            adapter="aws_identity_center",
        )
        log.info("remove_entitlement_started")

        if entitlement_type != "group":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"Unsupported entitlement_type: {entitlement_type}",
                error_code="UNSUPPORTED_ENTITLEMENT_TYPE",
            )

        id_result = self._find_user_id(user_email)
        if not id_result.is_success:
            if id_result.status == OperationStatus.NOT_FOUND:
                log.info("remove_entitlement_user_absent")
                return OperationResult.success(
                    message="user_absent_entitlement_skipped"
                )
            return id_result
        user_id: str = (id_result.data or {}).get("user_id", "")

        membership_result = self._aws.identitystore.get_group_membership_id(
            group_id=entitlement_id,
            member_id={"UserId": user_id},
        )
        if not membership_result.is_success:
            if membership_result.status == OperationStatus.NOT_FOUND:
                log.info("remove_entitlement_not_member", group_id=entitlement_id)
                return OperationResult.success(
                    message="group_membership_already_absent"
                )
            return membership_result

        membership_id: str = (membership_result.data or {}).get("MembershipId", "")
        result = self._aws.identitystore.delete_group_membership(
            membership_id=membership_id,
        )
        if result.is_success:
            log.info("remove_entitlement_removed", group_id=entitlement_id)
        else:
            log.error("remove_entitlement_failed", error=result.message)
        return result

    def fetch_current_state(self, user_email: str) -> OperationResult:
        """Fetch all current group memberships for a user.

        Returns SUCCESS with data={"user_id": str, "group_ids": list[str]}.
        """
        log = logger.bind(user_email=user_email, adapter="aws_identity_center")
        log.info("fetch_current_state_started")

        id_result = self._find_user_id(user_email)
        if not id_result.is_success:
            return id_result
        user_id = (id_result.data or {}).get("user_id", "")

        result = self._aws.identitystore.list_group_memberships_for_member(
            member_id={"UserId": user_id},
        )
        if not result.is_success:
            log.error("fetch_current_state_failed", error=result.message)
            return result

        memberships: List[Mapping[str, Any]] = (
            [item for item in result.data if isinstance(item, dict)]
            if isinstance(result.data, list)
            else []
        )
        group_ids = [
            group_id
            for membership in memberships
            for group_id in [membership.get("GroupId")]
            if isinstance(group_id, str) and group_id
        ]
        log.info("fetch_current_state_ok", group_count=len(group_ids))
        return OperationResult.success(
            data={"user_id": user_id, "group_ids": group_ids}
        )

    def get_current_entitlement_ids(self, user_email: str) -> OperationResult:
        """Return the set of AWS IC GroupIds the user currently belongs to.

        Entitlement IDs match ``EntitlementRule.entitlement_id`` (AWS IC GroupId)
        so the PolicyEngine can compute the desired-vs-current delta without
        additional parsing.

        Returns:
            ``OperationResult[Set[str]]`` with the group ID set, or error.
            Returns NOT_FOUND when the user does not exist in Identity Store.
        """
        log = logger.bind(user_email=user_email, adapter="aws_identity_center")

        state_result = self.fetch_current_state(user_email)
        if not state_result.is_success:
            return state_result

        group_ids: Set[str] = set((state_result.data or {}).get("group_ids", []))
        log.info("get_current_entitlement_ids_ok", count=len(group_ids))
        return OperationResult.success(data=group_ids)

    def list_all_provisioned_users(self) -> OperationResult:
        """Return the set of all user emails provisioned in AWS Identity Store.

        Used by reconciliation for orphan detection.  Iterates all users once
        and extracts the primary email from each record.

        Returns:
            ``OperationResult[Set[str]]`` of lowercase emails, or error.
        """
        log = logger.bind(adapter="aws_identity_center")
        log.info("list_all_provisioned_users_started")

        result = self._list_users()
        if not result.is_success:
            log.error("list_all_provisioned_users_failed", error=result.message)
            return result

        emails: Set[str] = set()
        users = result.data if isinstance(result.data, list) else []
        for user in users:
            email = self._extract_primary_email(user)
            if email is not None:
                emails.add(email)

        log.info("list_all_provisioned_users_ok", count=len(emails))
        return OperationResult.success(data=emails)

    def list_group_members(self, group_id: str) -> OperationResult:
        """Return the set of user emails that are members of an AWS IC group.

        Used by reconciliation batch read phase.  Resolves UserId → email via
        a single list_users call to avoid N per-user describe calls.

        Args:
            group_id: AWS IC GroupId.

        Returns:
            ``OperationResult[Set[str]]`` of lowercase member emails, or error.
        """
        log = logger.bind(group_id=group_id, adapter="aws_identity_center")
        log.info("list_group_members_started")

        memberships_result = self._aws.identitystore.list_group_memberships(
            group_id=group_id
        )
        if not memberships_result.is_success:
            log.error("list_group_memberships_failed", error=memberships_result.message)
            return memberships_result

        memberships: List[Mapping[str, Any]] = (
            [item for item in memberships_result.data if isinstance(item, dict)]
            if isinstance(memberships_result.data, list)
            else []
        )
        member_user_ids: Set[str] = {
            user_id
            for membership in memberships
            for member_id in [membership.get("MemberId")]
            if isinstance(member_id, dict)
            for user_id in [member_id.get("UserId")]
            if isinstance(user_id, str) and user_id
        }

        if not member_user_ids:
            return OperationResult.success(data=set())

        map_result = self._build_user_id_email_map()
        if not map_result.is_success:
            return map_result
        user_id_to_email: Dict[str, str] = (
            map_result.data if isinstance(map_result.data, dict) else {}
        )

        member_emails: Set[str] = {
            user_id_to_email[uid] for uid in member_user_ids if uid in user_id_to_email
        }
        log.info("list_group_members_ok", count=len(member_emails))
        return OperationResult.success(data=member_emails)

    def list_members_for_groups(self, group_ids: Set[str]) -> OperationResult:
        """Return group_id -> member email set using a bulk read path.

        Prefers the infrastructure client's list_groups_with_memberships orchestration
        when available, then falls back to per-group list_group_members reads.
        """
        if not group_ids:
            return OperationResult.success(data={})

        log = logger.bind(adapter="aws_identity_center", group_count=len(group_ids))
        identitystore = self._aws.identitystore

        if hasattr(identitystore, "list_groups_with_memberships"):
            target_ids = set(group_ids)
            bulk_result = identitystore.list_groups_with_memberships(
                groups_filters=[
                    lambda group: isinstance(group, dict)
                    and group.get("GroupId") in target_ids
                ]
            )
            if bulk_result.is_success and isinstance(bulk_result.data, list):
                mapping: Dict[str, Set[str]] = {}
                for group in bulk_result.data:
                    if not isinstance(group, dict):
                        continue
                    group_id = group.get("GroupId")
                    if not isinstance(group_id, str) or group_id not in target_ids:
                        continue

                    members = group.get("GroupMemberships", [])
                    emails: Set[str] = set()
                    if isinstance(members, list):
                        for membership in members:
                            if not isinstance(membership, dict):
                                continue
                            details = membership.get("UserDetails")
                            if isinstance(details, dict):
                                email = self._extract_primary_email(details)
                                if email is not None:
                                    emails.add(email)
                    mapping[group_id] = emails

                for group_id in target_ids:
                    mapping.setdefault(group_id, set())

                log.info("list_members_for_groups_ok", groups=len(mapping))
                return OperationResult.success(data=mapping)

            log.warning(
                "list_members_for_groups_bulk_failed",
                error=bulk_result.message,
            )

        fallback_mapping: Dict[str, Set[str]] = {}
        for group_id in group_ids:
            result = self.list_group_members(group_id)
            if not result.is_success:
                return result
            members = result.data if isinstance(result.data, set) else set()
            fallback_mapping[group_id] = {
                email for email in members if isinstance(email, str)
            }

        log.info("list_members_for_groups_ok_fallback", groups=len(fallback_mapping))
        return OperationResult.success(data=fallback_mapping)

    def _build_user_id_email_map(self) -> OperationResult:
        """Build a UserId → primary email mapping from all identity store users.

        Returns:
            ``OperationResult[Dict[str, str]]`` mapping UserId → lowercase email.
        """
        result = self._list_users()
        if not result.is_success:
            return result

        mapping: Dict[str, str] = {}
        users = result.data if isinstance(result.data, list) else []
        for user in users:
            user_id = user.get("UserId", "")
            if not isinstance(user_id, str) or not user_id:
                continue
            email = self._extract_primary_email(user)
            if email is not None:
                mapping[user_id] = email
        return OperationResult.success(data=mapping)
