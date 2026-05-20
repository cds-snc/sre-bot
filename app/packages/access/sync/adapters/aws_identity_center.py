"""AWS Identity Center adapter — group membership sync.

Maps normalized Access Sync actions to AWS IdentityStore API calls.
All external API calls are wrapped in try/except and return OperationResult.
Clients are injected from infrastructure.clients — never instantiated locally.

Entitlement model: entitlement_type="group", entitlement_id=AWS IC GroupId (UUID).
Group sync maps IDP security groups → AWS IC groups via group membership.

AWS IC has no native "disable" state; disable_user signals manual_action_required.
"""

import re
from dataclasses import dataclass, field, replace as dc_replace
from typing import Any, Dict, List, Mapping, Optional, Set

import structlog

from infrastructure.clients.aws import AWSClients
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.domain import (
    AdapterAssessment,
    CurrentPlatformState,
    DesiredPlatformState,
    DesiredUserState,
    ReconciliationOutcome,
    SyncOutcome,
)
from packages.access.sync.policies import (
    AdapterCapabilities,
    EntitlementRule,
    PlannedAction,
    PlanningContext,
    PlatformActionPlan,
    PlatformReconciliationPlanner,
    PolicyEngine,
)

logger = structlog.get_logger()

_AWS_GROUP_ID_PATTERN = re.compile(
    r"^([0-9a-f]{10}-|)[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}$"
)


def normalize_group_name(value: str) -> str:
    """Normalize a group display name for case-insensitive comparison."""
    return value.strip().casefold()


def _looks_like_group_id(value: str) -> bool:
    """Return whether the token matches AWS Identity Store GroupId shape."""
    return bool(_AWS_GROUP_ID_PATTERN.match(value.strip()))


@dataclass(frozen=True)
class _AwsGroupIndex:
    """Immutable index of AWS Identity Center groups built from a single list call."""

    by_id: Dict[str, str] = field(default_factory=dict)
    by_display_name_exact: Dict[str, str] = field(default_factory=dict)
    by_display_name_norm: Dict[str, Set[str]] = field(default_factory=dict)


class AwsIdentityCenterAdapter:
    """AWS Identity Center adapter.

    Uses pre-configured centralized AWSClients to access IdentityStore and SsoAdmin.
    All external API calls wrapped in try/except, returning OperationResult.

    The AWSClients facade is received fully configured with AWS_SSO_INSTANCE_ID bootstrap
    setting applied to the underlying IdentityStoreClient. No additional configuration
    is needed at the feature layer—the client is ready to use.

    Args:
        aws_clients: Centralized AWS clients facade from infrastructure.clients.aws.get_aws_clients
            Must have been initialized with AWS_SSO_INSTANCE_ID bootstrap setting.
    """

    def __init__(self, aws_clients: AWSClients) -> None:
        self._aws = aws_clients
        self._group_id_cache: Dict[str, str] = {}
        self._group_index: Optional[_AwsGroupIndex] = None

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
            supports_bulk_user_delta=True,
        )

    def canonicalize_entitlement_id(
        self,
        entitlement_type: str,
        entitlement_id: str,
    ) -> OperationResult:
        """Canonicalize entitlement IDs for planner comparisons.

        For AWS group entitlements this accepts either a GroupId or a
        display-name token and always returns the GroupId.
        """
        if entitlement_type != "group":
            return OperationResult.success(data=entitlement_id)

        return self._resolve_group_id(entitlement_id)

    def _build_group_index(self) -> OperationResult:
        """Build and cache a one-time group name index from list_groups.

        The index supports exact and normalized (casefold) display-name lookups
        and is stored on the adapter instance for its lifetime.

        Returns:
            OperationResult[_AwsGroupIndex] or error.
        """
        log = logger.bind(adapter="aws_identity_center")
        log.info("build_group_index_started")

        result = self._aws.identitystore.list_groups()
        if not result.is_success:
            log.error("build_group_index_failed", error=result.message)
            return result

        groups: List[Mapping[str, Any]] = (
            [item for item in result.data if isinstance(item, dict)]
            if isinstance(result.data, list)
            else []
        )

        by_id: Dict[str, str] = {}
        by_display_name_exact: Dict[str, str] = {}
        by_display_name_norm: Dict[str, Set[str]] = {}

        for group in groups:
            group_id = group.get("GroupId")
            display_name = group.get("DisplayName")
            if not isinstance(group_id, str) or not group_id:
                continue
            if not isinstance(display_name, str) or not display_name:
                continue

            by_id[group_id] = display_name
            by_display_name_exact[display_name] = group_id

            norm = normalize_group_name(display_name)
            by_display_name_norm.setdefault(norm, set()).add(group_id)

        index = _AwsGroupIndex(
            by_id=by_id,
            by_display_name_exact=by_display_name_exact,
            by_display_name_norm=by_display_name_norm,
        )
        self._group_index = index
        log.info("build_group_index_ok", group_count=len(by_id))
        return OperationResult.success(data=index)

    def _get_group_index(self) -> OperationResult:
        """Return the cached group index, building it on first access."""
        if self._group_index is not None:
            return OperationResult.success(data=self._group_index)
        return self._build_group_index()

    def _resolve_group_id(self, entitlement_id: str) -> OperationResult:
        """Resolve a group identifier to canonical AWS Identity Store GroupId.

        Tokens arrive pre-stripped by ``resolve_effective_policy`` (e.g.
        ``"finops-readonly"`` not ``"sg-aws-finops-readonly"``).  Resolution
        precedence:

        1. UUID-shaped input: verify via describe_group and return as-is.
        2. Exact display-name match in group index.
        3. Normalized (casefold) display-name match — single result only.
        4. Multiple normalized matches -> AMBIGUOUS_GROUP_NAME error.
        5. No match -> GROUP_ID_NOT_FOUND error.
        """
        log = logger.bind(adapter="aws_identity_center", entitlement_id=entitlement_id)
        candidate = entitlement_id.strip()
        if not candidate:
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Entitlement ID is required",
                error_code="INVALID_ENTITLEMENT_ID",
            )

        cached = self._group_id_cache.get(candidate)
        if cached is not None:
            return OperationResult.success(data=cached)

        # Step 1: UUID-shaped token — verify with describe_group.
        if _looks_like_group_id(candidate):
            describe_result = self._aws.identitystore.describe_group(group_id=candidate)
            if describe_result.is_success:
                self._group_id_cache[candidate] = candidate
                log.info("resolve_group_id_uuid", group_id=candidate)
                return OperationResult.success(data=candidate)

        # Steps 2-5: name-based lookup via group index.
        index_result = self._get_group_index()
        if not index_result.is_success:
            return index_result
        if not isinstance(index_result.data, _AwsGroupIndex):
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message="Unexpected group index type",
                error_code="INVALID_GROUP_INDEX",
            )
        index: _AwsGroupIndex = index_result.data

        # Step 2: exact display-name match (case-sensitive).
        token = candidate
        exact_group_id = index.by_display_name_exact.get(token)
        if exact_group_id is not None:
            self._group_id_cache[candidate] = exact_group_id
            log.info(
                "resolve_group_id_exact_name", group_id=exact_group_id, token=token
            )
            return OperationResult.success(data=exact_group_id)

        # Step 3 & 4: normalized display-name match.
        norm_token = normalize_group_name(token)
        matching_ids = index.by_display_name_norm.get(norm_token, set())

        if len(matching_ids) == 1:
            group_id = next(iter(matching_ids))
            self._group_id_cache[candidate] = group_id
            log.warning(
                "resolve_group_id_normalized_name",
                group_id=group_id,
                token=token,
                norm_token=norm_token,
            )
            return OperationResult.success(data=group_id)

        if len(matching_ids) > 1:
            log.error(
                "resolve_group_id_ambiguous",
                token=token,
                norm_token=norm_token,
                matching_count=len(matching_ids),
            )
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=(
                    f"Ambiguous group name '{token}': {len(matching_ids)} AWS IC groups "
                    f"normalize to the same token."
                ),
                error_code="AMBIGUOUS_GROUP_NAME",
            )

        # Step 5: not found.
        log.error("resolve_group_id_not_found", token=token)
        return OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message=f"No AWS IC group found for entitlement token: {token}",
            error_code="GROUP_ID_NOT_FOUND",
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

        group_id_result = self._resolve_group_id(entitlement_id)
        if not group_id_result.is_success:
            return group_id_result
        group_id = str(group_id_result.data)

        # Check if already a member (idempotency).
        membership_result = self._aws.identitystore.get_group_membership_id(
            group_id=group_id,
            member_id={"UserId": user_id},
        )
        if membership_result.is_success:
            log.info("apply_entitlement_already_member", group_id=group_id)
            return OperationResult.success(message="group_membership_already_exists")
        if membership_result.status != OperationStatus.NOT_FOUND:
            return membership_result

        result = self._aws.identitystore.create_group_membership(
            GroupId=group_id,
            MemberId={"UserId": user_id},
        )
        if result.is_success:
            log.info("apply_entitlement_added", group_id=group_id)
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

        group_id_result = self._resolve_group_id(entitlement_id)
        if not group_id_result.is_success:
            return group_id_result
        group_id = str(group_id_result.data)

        membership_result = self._aws.identitystore.get_group_membership_id(
            group_id=group_id,
            member_id={"UserId": user_id},
        )
        if not membership_result.is_success:
            if membership_result.status == OperationStatus.NOT_FOUND:
                log.info("remove_entitlement_not_member", group_id=group_id)
                return OperationResult.success(
                    message="group_membership_already_absent"
                )
            return membership_result

        membership_id: str = (membership_result.data or {}).get("MembershipId", "")
        result = self._aws.identitystore.delete_group_membership(
            membership_id=membership_id,
        )
        if result.is_success:
            log.info("remove_entitlement_removed", group_id=group_id)
        else:
            log.error("remove_entitlement_failed", error=result.message)
        return result

    def _fetch_current_state(self, user_email: str) -> OperationResult:
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

    def list_all_provisioned_users(self) -> OperationResult:
        """Return the set of all user emails provisioned in AWS Identity Store.

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
        resolved_group_id_result = self._resolve_group_id(group_id)
        if not resolved_group_id_result.is_success:
            return resolved_group_id_result
        resolved_group_id = str(resolved_group_id_result.data)

        log = logger.bind(group_id=resolved_group_id, adapter="aws_identity_center")
        log.info("list_group_members_started")

        memberships_result = self._aws.identitystore.list_group_memberships(
            group_id=resolved_group_id
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

        resolved_group_ids_result = self._resolve_group_ids(group_ids)
        if not resolved_group_ids_result.is_success or not isinstance(
            resolved_group_ids_result.data, set
        ):
            return resolved_group_ids_result
        resolved_group_ids = resolved_group_ids_result.data

        log = logger.bind(
            adapter="aws_identity_center",
            group_count=len(resolved_group_ids),
        )
        bulk_mapping_result = self._list_members_for_groups_bulk(resolved_group_ids)
        if bulk_mapping_result.is_success and isinstance(
            bulk_mapping_result.data, dict
        ):
            log.info("list_members_for_groups_ok", groups=len(bulk_mapping_result.data))
            return bulk_mapping_result
        if not bulk_mapping_result.is_success:
            log.warning(
                "list_members_for_groups_bulk_failed",
                error=bulk_mapping_result.message,
            )

        fallback_mapping: Dict[str, Set[str]] = {}
        for group_id in resolved_group_ids:
            result = self.list_group_members(group_id)
            if not result.is_success:
                return result
            members = result.data if isinstance(result.data, set) else set()
            fallback_mapping[group_id] = {
                email for email in members if isinstance(email, str)
            }

        log.info("list_members_for_groups_ok_fallback", groups=len(fallback_mapping))
        return OperationResult.success(data=fallback_mapping)

    def _resolve_group_ids(self, group_ids: Set[str]) -> OperationResult:
        """Resolve many group identifiers to canonical GroupIds."""
        resolved_group_ids: Set[str] = set()
        for group_identifier in group_ids:
            resolved_result = self._resolve_group_id(group_identifier)
            if not resolved_result.is_success or not isinstance(
                resolved_result.data, str
            ):
                return resolved_result
            resolved_group_ids.add(resolved_result.data)
        return OperationResult.success(data=resolved_group_ids)

    def _list_members_for_groups_bulk(  # noqa: C901
        self, group_ids: Set[str]
    ) -> OperationResult:
        """Attempt one bulk list path for many groups."""
        identitystore = self._aws.identitystore
        if not hasattr(identitystore, "list_groups_with_memberships"):
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message="bulk_memberships_unsupported",
                error_code="BULK_MEMBERSHIPS_UNSUPPORTED",
            )

        target_ids = set(group_ids)
        bulk_result = identitystore.list_groups_with_memberships(
            groups_filters=[
                lambda group: isinstance(group, dict)
                and group.get("GroupId") in target_ids
            ]
        )
        if not bulk_result.is_success or not isinstance(bulk_result.data, list):
            return bulk_result

        mapping: Dict[str, Set[str]] = {}
        user_ids_by_group: Dict[str, Set[str]] = {}
        for group in bulk_result.data:
            if not isinstance(group, dict):
                continue
            group_identifier = group.get("GroupId")
            if (
                not isinstance(group_identifier, str)
                or group_identifier not in target_ids
            ):
                continue
            members = group.get("GroupMemberships", [])
            emails: Set[str] = set()
            pending_user_ids: Set[str] = set()
            if isinstance(members, list):
                for membership in members:
                    if not isinstance(membership, dict):
                        continue
                    details = membership.get("UserDetails")
                    if isinstance(details, dict):
                        email = self._extract_primary_email(details)
                        if email is not None:
                            emails.add(email)
                            continue

                    member_id = membership.get("MemberId")
                    if isinstance(member_id, dict):
                        user_id = member_id.get("UserId")
                        if isinstance(user_id, str) and user_id:
                            pending_user_ids.add(user_id)
            mapping[group_identifier] = emails
            user_ids_by_group[group_identifier] = pending_user_ids

        unresolved_user_ids = {
            user_id for user_ids in user_ids_by_group.values() for user_id in user_ids
        }
        if unresolved_user_ids:
            user_map_result = self._build_user_id_email_map()
            if not user_map_result.is_success or not isinstance(
                user_map_result.data, dict
            ):
                return user_map_result
            user_id_to_email: Dict[str, str] = user_map_result.data

            for group_identifier, pending_user_ids in user_ids_by_group.items():
                mapping.setdefault(group_identifier, set()).update(
                    user_id_to_email[user_id]
                    for user_id in pending_user_ids
                    if user_id in user_id_to_email
                )

        for group_identifier in target_ids:
            mapping.setdefault(group_identifier, set())

        return OperationResult.success(data=mapping)

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

    # ------------------------------------------------------------------
    # Adapter-internal planning helpers
    # ------------------------------------------------------------------

    def _canonicalize_rules(
        self,
        rules: List[EntitlementRule],
    ) -> OperationResult:
        """Resolve entitlement tokens to canonical AWS IC GroupIds.

        Returns OperationResult[List[EntitlementRule]] with IDs resolved.
        Rules that cannot be resolved (GROUP_ID_NOT_FOUND, AMBIGUOUS_GROUP_NAME)
        are skipped with a warning; other errors are hard failures.
        """
        _SKIP_CODES = frozenset({"GROUP_ID_NOT_FOUND", "AMBIGUOUS_GROUP_NAME"})
        log = logger.bind(adapter="aws_identity_center")
        canonical: List[EntitlementRule] = []
        for rule in rules:
            if rule.entitlement_type != "group":
                canonical.append(rule)
                continue
            result = self._resolve_group_id(rule.entitlement_id)
            if result.is_success and isinstance(result.data, str):
                canonical.append(
                    EntitlementRule(
                        group_slug=rule.group_slug,
                        entitlement_type=rule.entitlement_type,
                        entitlement_id=result.data,
                        mode=rule.mode,
                    )
                )
            elif result.error_code in _SKIP_CODES:
                log.error(
                    "canonicalize_entitlement_skipped",
                    entitlement_id=rule.entitlement_id,
                    error_code=result.error_code,
                )
            else:
                return OperationResult.error(
                    result.status,
                    message=result.message,
                    error_code=result.error_code,
                )
        return OperationResult.success(data=canonical)

    def _execute_planned_actions(
        self,
        user_email: str,
        planned: List[PlannedAction],
    ) -> OperationResult:
        """Execute a list of planned actions; return SyncOutcome or error."""
        applied: List[str] = []
        requires_manual_action = False
        for action in planned:
            if action.action == "provision_user":
                result = self.ensure_user(user_email)
            elif action.action == "disable_user":
                result = self.disable_user(user_email)
            elif action.action == "remove_user":
                result = self.remove_user(user_email)
            elif action.action in ("apply_entitlement", "remove_entitlement"):
                if action.entitlement_type is None or action.entitlement_id is None:
                    return OperationResult.error(
                        OperationStatus.PERMANENT_ERROR,
                        message="Missing entitlement metadata",
                        error_code="INVALID_PLANNED_ACTION",
                    )
                if action.action == "apply_entitlement":
                    result = self.apply_entitlement(
                        user_email, action.entitlement_type, action.entitlement_id
                    )
                else:
                    result = self.remove_entitlement(
                        user_email, action.entitlement_type, action.entitlement_id
                    )
            else:
                return OperationResult.error(
                    OperationStatus.PERMANENT_ERROR,
                    message=f"Unknown action: {action.action}",
                    error_code="UNKNOWN_ACTION",
                )

            if result.is_success:
                applied.append(action.action)
            elif result.error_code == "UNSUPPORTED_OPERATION":
                requires_manual_action = True
            else:
                return OperationResult.error(
                    result.status,
                    message=result.message,
                    error_code=result.error_code,
                )

        return OperationResult.success(
            data=SyncOutcome(
                planned_actions=[a.action for a in planned],
                applied_actions=applied,
                requires_manual_action=requires_manual_action,
            )
        )

    def _log_platform_reconcile_summary(
        self,
        log: Any,
        dry_run: bool,
        plan: PlatformActionPlan,
        entitlement_slug_by_id: Dict[str, str],
        unchanged_user_count: int,
    ) -> None:
        """Emit a concise slug-first summary for full-platform reconciliation."""
        changed_users: Set[str] = (
            set(plan.users_to_provision)
            | set(plan.users_to_disable)
            | set(plan.users_to_remove)
        )
        for members in plan.entitlement_adds_by_id.values():
            changed_users.update(members)
        for members in plan.entitlement_removes_by_id.values():
            changed_users.update(members)

        log.info(
            "reconcile_platform_plan_summary",
            dry_run=dry_run,
            changed_user_count=len(changed_users),
            unchanged_user_count=unchanged_user_count,
            action_counts={
                "apply_entitlement": sum(
                    len(members) for members in plan.entitlement_adds_by_id.values()
                ),
                "disable_user": len(plan.users_to_disable),
                "provision_user": len(plan.users_to_provision),
                "remove_entitlement": sum(
                    len(members) for members in plan.entitlement_removes_by_id.values()
                ),
                "remove_user": len(plan.users_to_remove),
            },
            lifecycle_actions={
                "disable_user": sorted(plan.users_to_disable),
                "provision_user": sorted(plan.users_to_provision),
                "remove_user": sorted(plan.users_to_remove),
            },
            entitlements_by_action={
                "apply_entitlement": {
                    entitlement_slug_by_id.get(entitlement_id, entitlement_id): sorted(
                        members
                    )
                    for entitlement_id, members in sorted(
                        plan.entitlement_adds_by_id.items()
                    )
                },
                "remove_entitlement": {
                    entitlement_slug_by_id.get(entitlement_id, entitlement_id): sorted(
                        members
                    )
                    for entitlement_id, members in sorted(
                        plan.entitlement_removes_by_id.items()
                    )
                },
            },
        )

    def _build_canonical_platform_state(
        self,
        desired_state: DesiredPlatformState,
        canonical_rules: List[EntitlementRule],
    ) -> DesiredPlatformState:
        """Translate desired platform state to canonical AWS group IDs."""
        canonical_id_by_slug: Dict[str, str] = {
            rule.group_slug: rule.entitlement_id
            for rule in canonical_rules
            if rule.entitlement_type == "group"
        }
        desired_members_by_entitlement: Dict[str, Set[str]] = {
            canonical_id: set() for canonical_id in canonical_id_by_slug.values()
        }
        entitlement_slug_by_id: Dict[str, str] = {
            canonical_id: slug for slug, canonical_id in canonical_id_by_slug.items()
        }

        for (
            entitlement_id,
            members,
        ) in desired_state.desired_members_by_entitlement.items():
            slug = desired_state.entitlement_slug_by_id.get(entitlement_id)
            if slug is None:
                continue
            canonical_id = canonical_id_by_slug.get(slug)
            if canonical_id is None:
                continue
            desired_members_by_entitlement.setdefault(canonical_id, set()).update(
                member.lower() for member in members
            )

        return DesiredPlatformState(
            desired_users={email.lower() for email in desired_state.desired_users},
            desired_members_by_entitlement=desired_members_by_entitlement,
            entitlement_slug_by_id=entitlement_slug_by_id,
        )

    def _build_current_platform_state(
        self,
        managed_entitlement_ids: Set[str],
    ) -> OperationResult:
        """Read current AWS users and entitlement memberships once per run."""
        provisioned_result = self.list_all_provisioned_users()
        if not provisioned_result.is_success or not isinstance(
            provisioned_result.data, set
        ):
            return provisioned_result

        current_members_by_entitlement: Dict[str, Set[str]] = {}
        if managed_entitlement_ids:
            memberships_result = self.list_members_for_groups(managed_entitlement_ids)
            if not memberships_result.is_success or not isinstance(
                memberships_result.data, dict
            ):
                return memberships_result
            current_members_by_entitlement = {
                entitlement_id: {
                    email.lower() for email in members if isinstance(email, str)
                }
                for entitlement_id, members in memberships_result.data.items()
            }

        return OperationResult.success(
            data=CurrentPlatformState(
                current_users={
                    email.lower()
                    for email in provisioned_result.data
                    if isinstance(email, str)
                },
                current_members_by_entitlement=current_members_by_entitlement,
            )
        )

    def _build_user_action_map(
        self,
        plan: PlatformActionPlan,
    ) -> Dict[str, List[PlannedAction]]:
        """Translate grouped platform deltas into targeted per-user actions."""
        actions_by_user: Dict[str, List[PlannedAction]] = {}

        for user_email in sorted(plan.users_to_provision):
            actions_by_user.setdefault(user_email, []).append(
                PlannedAction(action="provision_user")
            )
        for entitlement_id, members in sorted(plan.entitlement_adds_by_id.items()):
            for user_email in sorted(members):
                actions_by_user.setdefault(user_email, []).append(
                    PlannedAction(
                        action="apply_entitlement",
                        entitlement_type="group",
                        entitlement_id=entitlement_id,
                    )
                )
        for entitlement_id, members in sorted(plan.entitlement_removes_by_id.items()):
            for user_email in sorted(members):
                actions_by_user.setdefault(user_email, []).append(
                    PlannedAction(
                        action="remove_entitlement",
                        entitlement_type="group",
                        entitlement_id=entitlement_id,
                    )
                )
        for user_email in sorted(plan.users_to_disable):
            actions_by_user.setdefault(user_email, []).append(
                PlannedAction(action="disable_user")
            )
        for user_email in sorted(plan.users_to_remove):
            actions_by_user.setdefault(user_email, []).append(
                PlannedAction(action="remove_user")
            )

        return actions_by_user

    # ------------------------------------------------------------------
    # Primary reconciliation interface
    # ------------------------------------------------------------------

    def reconcile_user(
        self,
        user_email: str,
        desired_state: DesiredUserState,
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        """Assess current state, plan delta, execute changes for one user."""
        log = logger.bind(
            user_email=user_email,
            platform=context.platform,
            adapter="aws_identity_center",
        )
        log.info(
            "reconcile_user_started",
            user_should_exist=desired_state.user_should_exist,
        )

        canon_result = self._canonicalize_rules(context.entitlement_rules)
        if not canon_result.is_success or not isinstance(canon_result.data, list):
            return canon_result
        canonical_rules: List[EntitlementRule] = canon_result.data

        required_result = self._canonicalize_rules(desired_state.required_entitlements)
        if not required_result.is_success or not isinstance(required_result.data, list):
            return required_result
        canonical_required: List[EntitlementRule] = required_result.data

        assessment = self._assess_live(user_email)
        if not assessment.is_success or assessment.data is None:
            return assessment
        current: AdapterAssessment = assessment.data

        canonical_context = dc_replace(context, entitlement_rules=canonical_rules)
        engine = PolicyEngine()
        planned = engine.plan_actions(
            policy=canonical_context,
            capabilities=self.capabilities(),
            user_should_exist=desired_state.user_should_exist,
            required_entitlements=canonical_required,
            current_entitlement_ids=current.current_entitlement_ids,
            platform_user_exists=current.platform_user_exists,
        )
        planned_names: List[str] = [a.action for a in planned]
        log.debug(
            "reconcile_user_plan_summary",
            dry_run=dry_run,
            user_should_exist=desired_state.user_should_exist,
            platform_user_exists=current.platform_user_exists,
            desired_entitlement_ids=sorted(
                rule.entitlement_id for rule in canonical_required
            ),
            current_entitlement_ids=sorted(current.current_entitlement_ids),
            planned_actions=planned_names,
        )
        log.info(
            "reconcile_user_planned",
            dry_run=dry_run,
            count=len(planned_names),
            actions=planned_names,
        )

        if dry_run:
            return OperationResult.success(
                data=SyncOutcome(
                    planned_actions=planned_names,
                    applied_actions=[],
                )
            )

        return self._execute_planned_actions(user_email, planned)

    def reconcile_platform(
        self,
        desired_state: DesiredPlatformState,
        context: PlanningContext,
        dry_run: bool = False,
    ) -> OperationResult:
        """Batch reconcile AWS Identity Center using entitlement-shaped state."""
        log = logger.bind(platform=context.platform, adapter="aws_identity_center")
        log.info("reconcile_platform_started", dry_run=dry_run)

        canon_result = self._canonicalize_rules(context.entitlement_rules)
        if not canon_result.is_success or not isinstance(canon_result.data, list):
            return canon_result
        canonical_rules: List[EntitlementRule] = canon_result.data
        canonical_context = dc_replace(context, entitlement_rules=canonical_rules)
        canonical_desired = self._build_canonical_platform_state(
            desired_state=desired_state,
            canonical_rules=canonical_rules,
        )

        current_state_result = self._build_current_platform_state(
            managed_entitlement_ids=set(
                canonical_desired.desired_members_by_entitlement.keys()
            )
        )
        if not current_state_result.is_success or not isinstance(
            current_state_result.data, CurrentPlatformState
        ):
            return current_state_result
        current_state: CurrentPlatformState = current_state_result.data

        planner = PlatformReconciliationPlanner()
        plan = planner.plan_platform_actions(
            desired_users=canonical_desired.desired_users,
            desired_members_by_entitlement=canonical_desired.desired_members_by_entitlement,
            current_users=current_state.current_users,
            current_members_by_entitlement=current_state.current_members_by_entitlement,
            authn_removal_mode=canonical_context.authn_removal_mode,
        )
        actions_by_user = self._build_user_action_map(plan)

        failed_group_slugs = sorted(
            set(desired_state.entitlement_slug_by_id.values())
            - set(canonical_desired.entitlement_slug_by_id.values())
        )
        log.info(
            "reconcile_platform_groups_matched",
            groups_discovered=len(desired_state.entitlement_slug_by_id),
            groups_canonicalized=len(canonical_desired.entitlement_slug_by_id),
            groups_failed=len(failed_group_slugs),
            failed_group_slugs=failed_group_slugs,
        )
        self._log_platform_reconcile_summary(
            log=log,
            dry_run=dry_run,
            plan=plan,
            entitlement_slug_by_id=canonical_desired.entitlement_slug_by_id,
            unchanged_user_count=len(
                canonical_desired.desired_users | current_state.current_users
            )
            - len(actions_by_user),
        )

        per_user: Dict[str, SyncOutcome] = {}
        users_converged = 0
        requires_manual_action_count = 0
        for user_email in sorted(actions_by_user):
            planned_actions = actions_by_user[user_email]
            if dry_run:
                outcome = SyncOutcome(
                    planned_actions=[action.action for action in planned_actions],
                    applied_actions=[],
                )
            else:
                exec_result = self._execute_planned_actions(user_email, planned_actions)
                if not exec_result.is_success or not isinstance(
                    exec_result.data, SyncOutcome
                ):
                    return exec_result
                outcome = exec_result.data
            per_user[user_email] = outcome
            if outcome.applied_actions:
                users_converged += 1
            if outcome.requires_manual_action:
                requires_manual_action_count += 1

        users_synced = len(
            canonical_desired.desired_users | current_state.current_users
        )
        orphans_found = len(
            current_state.current_users - canonical_desired.desired_users
        )
        log.info(
            "reconcile_platform_completed",
            users_synced=users_synced,
            users_converged=users_converged,
            orphans_found=orphans_found,
            dry_run=dry_run,
        )
        return OperationResult.success(
            data=ReconciliationOutcome(
                platform=context.platform,
                users_synced=users_synced,
                users_converged=users_converged,
                orphans_found=orphans_found,
                requires_manual_action_count=requires_manual_action_count,
                dry_run=dry_run,
                per_user=per_user,
                changed_user_count=len(actions_by_user),
                unchanged_user_count=len(
                    canonical_desired.desired_users | current_state.current_users
                )
                - len(actions_by_user),
                action_counts={
                    "apply_entitlement": sum(
                        len(members) for members in plan.entitlement_adds_by_id.values()
                    ),
                    "disable_user": len(plan.users_to_disable),
                    "provision_user": len(plan.users_to_provision),
                    "remove_entitlement": sum(
                        len(members)
                        for members in plan.entitlement_removes_by_id.values()
                    ),
                    "remove_user": len(plan.users_to_remove),
                },
                lifecycle_actions={
                    "disable_user": sorted(plan.users_to_disable),
                    "provision_user": sorted(plan.users_to_provision),
                    "remove_user": sorted(plan.users_to_remove),
                },
                entitlements_by_action={
                    "apply_entitlement": {
                        canonical_desired.entitlement_slug_by_id.get(
                            entitlement_id, entitlement_id
                        ): sorted(members)
                        for entitlement_id, members in sorted(
                            plan.entitlement_adds_by_id.items()
                        )
                    },
                    "remove_entitlement": {
                        canonical_desired.entitlement_slug_by_id.get(
                            entitlement_id, entitlement_id
                        ): sorted(members)
                        for entitlement_id, members in sorted(
                            plan.entitlement_removes_by_id.items()
                        )
                    },
                },
            )
        )

    def _assess_live(self, user_email: str) -> OperationResult:
        """Perform a live platform read and return AdapterAssessment."""
        state_result = self._fetch_current_state(user_email)
        if not state_result.is_success:
            if state_result.status == OperationStatus.NOT_FOUND:
                return OperationResult.success(
                    data=AdapterAssessment(
                        platform_user_exists=False,
                        current_entitlement_ids=set(),
                    )
                )
            return state_result
        group_ids: Set[str] = set((state_result.data or {}).get("group_ids", []))
        return OperationResult.success(
            data=AdapterAssessment(
                platform_user_exists=True,
                current_entitlement_ids=group_ids,
            )
        )
