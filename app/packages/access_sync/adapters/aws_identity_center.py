"""AWS Identity Center adapter — v1: group membership sync only.

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

import structlog

from typing import Dict, Set

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
        result = self._aws.identitystore.list_users(
            Filters=[{"AttributePath": "emails.value", "AttributeValue": user_email}],
        )
        if not result.is_success:
            log.error("find_user_failed", error=result.message)
            return result

        users_data: dict = result.data if isinstance(result.data, dict) else {}
        users = users_data.get("Users", [])
        if not users:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"User not found in Identity Store: {user_email}",
                error_code="USER_NOT_FOUND",
            )
        return OperationResult.success(data={"user_id": users[0]["UserId"]})

    def get_user(self, user_email: str) -> OperationResult:
        """Look up a user; returns NOT_FOUND if missing."""
        return self._find_user_id(user_email)

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

        result = self._aws.identitystore.create_user(
            UserName=user_email,
            DisplayName=user_email,
            Emails=[{"Value": user_email, "Primary": True, "Type": "work"}],
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

        memberships: list = result.data if isinstance(result.data, list) else []
        group_ids = [m.get("GroupId", "") for m in memberships if m.get("GroupId")]
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

        result = self._aws.identitystore.list_users()
        if not result.is_success:
            log.error("list_all_provisioned_users_failed", error=result.message)
            return result

        users: list = result.data if isinstance(result.data, list) else []
        emails: Set[str] = set()
        for user in users:
            for email_entry in user.get("Emails", []):
                if email_entry.get("Primary") and email_entry.get("Value"):
                    emails.add(email_entry["Value"].strip().lower())
                    break

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

        memberships: list = (
            memberships_result.data if isinstance(memberships_result.data, list) else []
        )
        member_user_ids: Set[str] = {
            m.get("MemberId", {}).get("UserId", "")
            for m in memberships
            if m.get("MemberId", {}).get("UserId")
        }

        if not member_user_ids:
            return OperationResult.success(data=set())

        map_result = self._build_user_id_email_map()
        if not map_result.is_success:
            return map_result
        user_id_to_email: Dict[str, str] = map_result.data or {}

        member_emails: Set[str] = {
            user_id_to_email[uid] for uid in member_user_ids if uid in user_id_to_email
        }
        log.info("list_group_members_ok", count=len(member_emails))
        return OperationResult.success(data=member_emails)

    def _build_user_id_email_map(self) -> OperationResult:
        """Build a UserId → primary email mapping from all identity store users.

        Returns:
            ``OperationResult[Dict[str, str]]`` mapping UserId → lowercase email.
        """
        result = self._aws.identitystore.list_users()
        if not result.is_success:
            return result

        users: list = result.data if isinstance(result.data, list) else []
        mapping: Dict[str, str] = {}
        for user in users:
            user_id = user.get("UserId", "")
            if not user_id:
                continue
            for email_entry in user.get("Emails", []):
                if email_entry.get("Primary") and email_entry.get("Value"):
                    mapping[user_id] = email_entry["Value"].strip().lower()
                    break
        return OperationResult.success(data=mapping)
