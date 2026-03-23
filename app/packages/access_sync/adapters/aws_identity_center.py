"""AWS Identity Center adapter.

Maps normalized Access Sync actions to AWS IdentityStore and SSO Admin API calls.
All external API calls are wrapped in try/except and return OperationResult.
Clients are injected from infrastructure.services — never instantiated locally.

Entitlement ID format for permission_set type:
    "<account_id>/<permission_set_name>"
    e.g. "123456789012/AWSAdministratorAccess"

This adapter handles the user-lifecycle contract (ensure_user, disable_user,
remove_user) and delegates entitlement management to SSO Admin account
assignments.  AWS IC has no native "disable" state at the identity-store level;
disable_user is therefore not supported and signals manual_action_required.
"""

import structlog

from typing import Set

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
            supported_entitlement_types={"permission_set"},
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
        """Apply a permission-set account assignment (idempotent).

        entitlement_id must be formatted as "<account_id>/<permission_set_arn>".
        """
        log = logger.bind(
            user_email=user_email,
            entitlement_type=entitlement_type,
            entitlement_id=entitlement_id,
            adapter="aws_identity_center",
        )
        log.info("apply_entitlement_started")

        if entitlement_type != "permission_set":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"Unsupported entitlement_type: {entitlement_type}",
                error_code="UNSUPPORTED_ENTITLEMENT_TYPE",
            )

        parts = entitlement_id.split("/", 1)
        if len(parts) != 2:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=(
                    "entitlement_id must be '<account_id>/<permission_set_arn>', "
                    f"got: {entitlement_id}"
                ),
                error_code="INVALID_ENTITLEMENT_ID",
            )

        account_id, permission_set_arn = parts

        id_result = self._find_user_id(user_email)
        if not id_result.is_success:
            return id_result
        user_id: str = (id_result.data or {}).get("user_id", "")

        result = self._aws.sso_admin.create_account_assignment(
            permission_set_arn=permission_set_arn,
            principal_id=user_id,
            principal_type="USER",
            target_id=account_id,
        )
        if result.is_success:
            log.info("apply_entitlement_assigned", account_id=account_id)
        else:
            log.error("apply_entitlement_failed", error=result.message)
        return result

    def remove_entitlement(
        self,
        user_email: str,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        """Remove a permission-set account assignment (idempotent).

        entitlement_id must be formatted as "<account_id>/<permission_set_arn>".
        """
        log = logger.bind(
            user_email=user_email,
            entitlement_type=entitlement_type,
            entitlement_id=entitlement_id,
            adapter="aws_identity_center",
        )
        log.info("remove_entitlement_started")

        if entitlement_type != "permission_set":
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"Unsupported entitlement_type: {entitlement_type}",
                error_code="UNSUPPORTED_ENTITLEMENT_TYPE",
            )

        parts = entitlement_id.split("/", 1)
        if len(parts) != 2:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=(
                    "entitlement_id must be '<account_id>/<permission_set_arn>', "
                    f"got: {entitlement_id}"
                ),
                error_code="INVALID_ENTITLEMENT_ID",
            )

        account_id, permission_set_arn = parts

        id_result = self._find_user_id(user_email)
        if not id_result.is_success:
            if id_result.status == OperationStatus.NOT_FOUND:
                log.info("remove_entitlement_user_absent")
                return OperationResult.success(
                    message="user_absent_entitlement_skipped"
                )
            return id_result
        user_id = (id_result.data or {}).get("user_id", "")

        result = self._aws.sso_admin.delete_account_assignment(
            permission_set_arn=permission_set_arn,
            principal_id=user_id,
            principal_type="USER",
            target_id=account_id,
        )
        if result.is_success:
            log.info("remove_entitlement_deleted", account_id=account_id)
        else:
            log.error("remove_entitlement_failed", error=result.message)
        return result

    def fetch_current_state(self, user_email: str) -> OperationResult:
        """Fetch all current account assignments for a user.

        Returns SUCCESS with data={"user_id": str, "assignments": list}.
        """
        log = logger.bind(user_email=user_email, adapter="aws_identity_center")
        log.info("fetch_current_state_started")

        id_result = self._find_user_id(user_email)
        if not id_result.is_success:
            return id_result
        user_id = (id_result.data or {}).get("user_id", "")

        result = self._aws.sso_admin.list_account_assignments(
            principal_id=user_id,
            principal_type="USER",
        )
        if not result.is_success:
            log.error("fetch_current_state_failed", error=result.message)
            return result

        assignments_data: dict = result.data if isinstance(result.data, dict) else {}
        assignments = assignments_data.get("AccountAssignments", [])
        log.info("fetch_current_state_ok", assignment_count=len(assignments))
        return OperationResult.success(
            data={"user_id": user_id, "assignments": assignments}
        )

    def get_current_entitlement_ids(self, user_email: str) -> OperationResult:
        """Return the normalised set of entitlement IDs the user currently holds.

        Each assignment is rendered as ``"{account_id}/{permission_set_arn}"`` ,
        matching ``EntitlementRule.entitlement_id`` format so the PolicyEngine
        can compute the desired-vs-current delta without any extra parsing.

        Returns:
            ``OperationResult[Set[str]]`` with the normalised ID set, or error.
            Returns NOT_FOUND when the user does not exist in Identity Store.
        """
        log = logger.bind(user_email=user_email, adapter="aws_identity_center")

        state_result = self.fetch_current_state(user_email)
        if not state_result.is_success:
            return state_result

        assignments = (state_result.data or {}).get("assignments", [])
        ids: Set[str] = set()
        for assignment in assignments:
            account_id = assignment.get("AccountId", "")
            permission_set_arn = assignment.get("PermissionSetArn", "")
            if account_id and permission_set_arn:
                ids.add(f"{account_id}/{permission_set_arn}")

        log.info("get_current_entitlement_ids_ok", count=len(ids))
        return OperationResult.success(data=ids)
