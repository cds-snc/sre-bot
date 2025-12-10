"""AWS Identity Center Provider"""

# Standard library
import re
from typing import Any, Dict, List, Optional

# Local application - infrastructure
from infrastructure.configuration import settings
from infrastructure.observability import get_module_logger

# Local application - integrations
from integrations.aws import identity_store_next as identity_store
from integrations.aws.schemas import Group as AwsGroup
from integrations.aws.schemas import GroupMembership as AwsGroupMembership
from integrations.aws.schemas import User as AwsUser

# Local application - modules
from modules.groups.domain.errors import IntegrationError
from modules.groups.domain.models import (
    NormalizedGroup,
    NormalizedMember,
    as_canonical_dict,
)
from modules.groups.providers import register_provider
from modules.groups.providers.base import (
    GroupProvider,
    HealthCheckResult,
    ProviderCapabilities,
    provider_operation,
    validate_member_email,
)
from infrastructure.operations import OperationResult
from infrastructure.operations.classifiers import classify_aws_error


logger = get_module_logger()

# AWS Identity Center resource IDs (GroupId, UserId, MembershipId) use UUID format
AWS_UUID_REGEX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


@register_provider("aws")
class AwsIdentityCenterProvider(GroupProvider):
    """AWS Identity Center provider implementing the GroupProvider contract.

    Third party provider: AWS Identity Center (successor to AWS SSO)

    Provider Type: SECONDARY (not authoritative)
    This provider is a secondary provider that synchronizes group membership from
    the primary provider (Google Workspace). It is NOT the source of truth for
    group data. All operations use email addresses as the universal identifier.

    Supported Operations:
    - User creation
    - User deletion
    - Membership creation
    - Membership deletion
    - Fetching groups
    - Listing group members

    Data Model:
    - Group IDs: AWS UUID format (e.g., 906abc12-d3e4-5678-90ab-cdef12345678)
    - User IDs: AWS UUID format
    - Membership IDs: AWS UUID format
    - Universal Identifier: Email address (used for cross-provider mapping)

    Note on Role Information:
    This provider returns role=None for all members because AWS Identity Center
    does not expose role information in its API. Role-based access control should
    be resolved through the primary provider (Google Workspace) which provides
    the provides_role_info capability.

    IMPORTANT: This provider is responsible for converting all AWS-specific
    schemas (AwsUser, AwsGroup) to canonical NormalizedMember and NormalizedGroup
    dataclasses. The provider owns all validation and conversion logic for its
    provider-specific data.
    """

    def __init__(self):
        """Initialize the provider with circuit breaker support."""
        super().__init__()
        self.identity_store_id = self._get_identity_store_id()

    def _get_identity_store_id(self) -> Optional[str]:
        """Get the AWS Identity Store ID from settings.

        Returns:
            Identity Store ID from settings, or None if not configured
        """
        if hasattr(settings, "aws") and hasattr(settings.aws, "INSTANCE_ID"):
            return settings.aws.INSTANCE_ID
        return None

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities."""
        return ProviderCapabilities(supports_member_management=True)

    def classify_error(self, exc: Exception) -> "OperationResult":
        """Classify AWS Identity Center API errors into OperationResult.

        Uses infrastructure classifier to standardize error handling across
        all AWS SDK integrations.

        Args:
            exc: Exception raised by AWS API

        Returns:
            OperationResult with appropriate status and error code
        """

        return classify_aws_error(exc)

    def _strip_provider_prefix(self, group_identifier: str) -> str:
        """Remove AWS prefix from group identifier to get canonical name.

        Handles email format from primary provider:
        - "aws-admins@example.com" -> "admins@example.com"
        - "aws-developers@example.com" -> "developers@example.com"
        - "developers@example.com" (no prefix) -> "developers@example.com"

        Also handles direct display names:
        - "aws-development-team" -> "development-team"
        - "development-team" (no prefix) -> "development-team"

        Args:
            group_identifier: Email, UUID, or display name with optional "aws-" prefix

        Returns:
            Identifier with "aws-" prefix removed (if present)
        """
        normalized = group_identifier.strip()

        # Known AWS prefix patterns
        prefixes = ["aws-", "aws_"]

        for prefix in prefixes:
            if normalized.lower().startswith(prefix):
                # Remove prefix, preserving case of remainder
                return normalized[len(prefix) :]

        return normalized

    # ------------------------------------------------------------------
    # Instance helpers (migrated from module-level into the provider)
    # ------------------------------------------------------------------
    def _extract_id_from_resp(
        self, resp: Any, id_keys: List[str], operation_name: str = "extract_id"
    ) -> str:
        """Extract an ID from an AWS integration response with explicit error handling.

        Validates response structure at each step and raises explicit exceptions
        rather than returning None silently.

        Args:
            resp: The integration response object
            id_keys: List of keys to check for ID values, in priority order
            operation_name: Name of the operation for error context

        Returns:
            The extracted ID string

        Raises:
            IntegrationError: If response is invalid or missing success attribute
            ValueError: If ID cannot be extracted from response data
        """
        # Step 1: Validate response object exists
        if resp is None:
            raise ValueError(f"{operation_name}: Response is None")

        # Step 2: Validate response has is_success property
        if not hasattr(resp, "is_success"):
            raise IntegrationError(
                f"{operation_name}: AWS identity_store returned unexpected type",
                response=resp,
            )

        # Step 3: Check if operation succeeded
        if not resp.is_success:
            raise IntegrationError(
                f"{operation_name}: AWS API call failed",
                response=resp,
            )

        # Step 4: Extract data from response
        data = resp.data
        if data is None:
            raise ValueError(f"{operation_name}: Response data is None")

        # Step 5: If data is string, return it directly
        if isinstance(data, str):
            if not data.strip():
                raise ValueError(f"{operation_name}: ID string is empty")
            return data.strip()

        # Step 6: If data is dict, search for ID in priority order
        if isinstance(data, dict):
            # Try primary id_keys first
            for k in id_keys:
                if k in data:
                    value = data[k]
                    if value and isinstance(value, str):
                        return value.strip()

            # Try nested MemberId structure
            if "MemberId" in data and isinstance(data["MemberId"], dict):
                user_id = data["MemberId"].get("UserId")
                if user_id:
                    return user_id

            # Fallback to UserId key
            if "UserId" in data:
                user_id = data.get("UserId")
                if user_id:
                    return user_id

            raise ValueError(
                f"{operation_name}: Could not extract ID from response data. "
                f"Expected one of {id_keys}, got keys: {list(data.keys())}"
            )

        # Step 7: Invalid data type
        raise ValueError(
            f"{operation_name}: Response data must be string or dict, "
            f"got {type(data).__name__}"
        )

    def _ensure_user_id_from_email(self, email: str) -> str:
        resp = identity_store.get_user_by_username(email)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws get_user_by_username returned unexpected type", response=resp
            )
        if not resp.is_success:
            raise IntegrationError("aws resolve user id failed", response=resp)
        uid = self._extract_id_from_resp(resp, ["UserId", "Id"], "get_user_by_username")
        return uid

    def _resolve_group_id(self, group_key: str) -> str:
        """Resolve a group identifier to AWS GroupId (UUID format).

        AWS Identity Center APIs accept either:
        - GroupId: UUID format (e.g., 906abc12-d3e4-5678-90ab-cdef12345678)
        - DisplayName: canonical name (e.g., digitaltransformationoffice-ai-staging-admin)
        - Email format: from primary provider (e.g., "aws-admins@example.com")

        Email handling:
        1. Strips provider prefix (aws-, google-, etc.) if present
        2. Extracts local part (before @) to get canonical name
        3. Uses canonical name to resolve UUID via get_group_by_name

        Args:
            group_key: UUID GroupId, display name, or email format

        Returns:
            AWS GroupId in UUID format

        Raises:
            IntegrationError: If group cannot be resolved
        """
        normalized = group_key.strip()

        # Check if input is already a UUID (GroupId format)
        if AWS_UUID_REGEX.match(normalized):
            return normalized

        # Handle email format: extract local part and strip provider prefix
        if "@" in normalized:
            # Extract local part (before @)
            local_part = normalized.split("@")[0]
            # Strip any provider prefix
            normalized = self._strip_provider_prefix(local_part)

        # At this point, normalized is a canonical display name
        # Resolve it to AWS GroupId using get_group_by_name
        resp = identity_store.get_group_by_name(normalized)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws get_group_by_name returned unexpected type", response=resp
            )
        if not resp.is_success:
            raise IntegrationError(
                f"aws resolve group id failed for display name: {normalized}",
                response=resp,
            )

        # Extract GroupId from response
        group_id = self._extract_id_from_resp(
            resp, ["GroupId", "Id"], "get_group_by_name"
        )
        return group_id

    def _resolve_membership_id(self, group_key: str, user_id: str) -> str:
        """Resolve the membership ID for a user in a group.
            AWS Identity Center APIs uses memberships to associate users to groups.

        Args:
            group_key: AWS group key (UUID or display name).
            user_id: AWS user ID.
        """
        resp = identity_store.get_group_membership_id(group_key, user_id)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws resolve membership id returned unexpected type", response=resp
            )
        if not resp.is_success:
            raise IntegrationError("aws resolve membership id failed", response=resp)
        mid = self._extract_id_from_resp(
            resp, ["MembershipId", "MembershipId"], "get_group_membership_id"
        )
        return mid

    def _fetch_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        resp = identity_store.get_user(user_id)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws get_user returned unexpected type", response=resp
            )
        if not resp.is_success:
            raise IntegrationError("aws get_user failed", response=resp)
        return resp.data or {}

    def _normalize_member_from_aws(
        self, member_data: dict, include_raw: bool = False
    ) -> NormalizedMember:
        """Convert an AWS member response to a NormalizedMember.

        This is AWS's responsibility: take its schema and produce the canonical
        normalized member contract.

        Args:
            member_data: A dict response from AWS Identity Store API. Could be GroupMembership or User object.

        Returns:
            A NormalizedMember instance.

        Raises:
            IntegrationError: If the member data is invalid for AWS's schema.
        """

        if "MembershipId" in member_data and "UserDetails" in member_data:
            try:
                gm = AwsGroupMembership.model_validate(member_data)
                details = gm.UserDetails if gm.UserDetails else AwsUser()
                provider_member_id = gm.MembershipId
            except Exception as exc:
                raise IntegrationError(
                    "aws group membership validation failed"
                ) from exc
        else:
            try:
                details = AwsUser.model_validate(member_data)
                provider_member_id = None
            except Exception as exc:
                raise IntegrationError("aws user validation failed") from exc

        return NormalizedMember(
            email=(
                details.Emails[0].Value
                if details.Emails and len(details.Emails) > 0
                else None
            ),
            id=details.UserId if details.UserId else None,
            role=None,
            provider_member_id=provider_member_id,
            first_name=(
                details.Name.GivenName.strip()
                if details.Name and details.Name.GivenName
                else None
            ),
            family_name=(
                details.Name.FamilyName.strip()
                if details.Name and details.Name.FamilyName
                else None
            ),
            raw=member_data if include_raw else None,
        )

    def _normalize_group_from_aws(
        self,
        group: dict,
        memberships: List[Dict] | None = None,
        include_raw: bool = False,
    ) -> NormalizedGroup:
        """Convert an AWS group response to a NormalizedGroup.

        This is AWS's responsibility: take its schema and produce the canonical
        normalized group contract.

        Args:
            group: A dict response from AWS Identity Store API.
            memberships: Optional pre-fetched member list to include in the group.

        Returns:
            A NormalizedGroup instance.

        Raises:
            IntegrationError: If the group data is invalid for AWS's schema.
        """
        try:
            g = AwsGroup.model_validate(group)
        except Exception as exc:
            raise IntegrationError("aws group validation failed") from exc

        gid = getattr(g, "GroupId", None)
        name = getattr(g, "DisplayName", None) or gid
        description = getattr(g, "Description", None)

        raw_memberships = memberships
        if raw_memberships is None:
            if isinstance(group, dict):
                raw_memberships = group.get("GroupMemberships")
            else:
                raw_memberships = None

        normalized_members = [
            self._normalize_member_from_aws(m)
            for m in (raw_memberships or [])
            if isinstance(m, dict)
        ]

        return NormalizedGroup(
            id=gid,
            name=name,
            description=description,
            provider="aws",
            members=normalized_members,
            raw=group if include_raw else None,
        )

    @provider_operation(data_key="result")
    def _add_member_impl(self, group_key: str, member_email: str) -> dict:
        """Add a member to a group by email.

        Args:
            group_key: AWS group key (UUID or display name).
            member_email: Email address of the member to add

        Returns:
            A canonical member dict (normalized NormalizedMember).
        """
        validated_email = validate_member_email(member_email)

        # Resolve group_key to UUID format
        resolved_group_id = self._resolve_group_id(group_key)

        user_id = self._ensure_user_id_from_email(validated_email)
        resp = identity_store.create_group_membership(resolved_group_id, user_id)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws create_group_membership returned unexpected type", response=resp
            )
        if not resp.is_success:
            raise IntegrationError("aws add_user_to_group failed", response=resp)
        try:
            user_data = self._fetch_user_details(user_id)
        except IntegrationError:
            user_data = None
        member_payload = {"email": validated_email, "id": user_id}
        if user_data:
            member_payload.update({"Name": user_data.get("Name") or {}})
        return as_canonical_dict(self._normalize_member_from_aws(member_payload))

    @provider_operation(data_key="result")
    def _remove_member_impl(self, group_key: str, member_email: str) -> dict:
        """Remove a member from a group by email.

        Args:
            group_key: AWS group key (UUID or display name).
            member_email: Email address of the member to remove

        Returns:
            A canonical member dict (normalized NormalizedMember).
        """
        validated_email = validate_member_email(member_email)

        # Resolve group_key to UUID format
        resolved_group_id = self._resolve_group_id(group_key)

        user_id = self._ensure_user_id_from_email(validated_email)
        membership_id = self._resolve_membership_id(resolved_group_id, user_id)
        resp = identity_store.delete_group_membership(membership_id)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws delete_group_membership returned unexpected type", response=resp
            )
        if not resp.is_success:
            raise IntegrationError("aws remove_user_from_group failed", response=resp)
        try:
            user_data = self._fetch_user_details(user_id)
        except IntegrationError:
            user_data = None
        member_payload = {"email": validated_email, "id": user_id}
        if user_data:
            member_payload.update({"Name": user_data.get("Name") or {}})
        return as_canonical_dict(self._normalize_member_from_aws(member_payload))

    def _extract_user_id_from_membership(self, membership: dict) -> Optional[str]:
        """Extract user ID from a group membership object.

        AWS GroupMembership may have MemberId as a dict with UserId field.

        Args:
            membership: Group membership dict from AWS

        Returns:
            User ID string, or None if not found

        Raises:
            ValueError: If membership structure is invalid
        """
        if not isinstance(membership, dict):
            return None

        if "MemberId" in membership and isinstance(membership["MemberId"], dict):
            user_id = membership["MemberId"].get("UserId")
            if user_id:
                return user_id

        return None

    def _extract_email_from_user_data(self, user_data: dict) -> Optional[str]:
        """Extract email from AWS user data.

        AWS returns emails in various formats depending on the API call.
        This method handles multiple formats.

        Args:
            user_data: User data dict from AWS

        Returns:
            Email string, or None if not found

        Raises:
            ValueError: If email structure is unexpected
        """
        if not isinstance(user_data, dict):
            return None

        # Try direct email field first
        if "email" in user_data and user_data["email"]:
            return user_data["email"]

        # Try Emails list structure (AWS common format)
        if isinstance(user_data.get("Emails"), list) and user_data["Emails"]:
            first_email = user_data["Emails"][0]
            if isinstance(first_email, dict) and first_email.get("Value"):
                return first_email["Value"]

        return None

    @provider_operation(data_key="members")
    def _get_group_members_impl(self, group_key: str, **kwargs) -> list[dict]:
        """Fetch group members with proper error handling for missing emails.

        Returns a list of normalized members. Members without email addresses
        are skipped with explicit logging to avoid data quality issues.

        Args:
            group_key: AWS group key (UUID or display name).
            **kwargs: Additional parameters (unused).

        Returns:
            List of canonical member dicts (normalized NormalizedMember).
        """
        # Resolve group_key to UUID format for consistency
        resolved_group_id = self._resolve_group_id(group_key)

        resp = identity_store.list_group_memberships(resolved_group_id)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws list_group_memberships returned unexpected type", response=resp
            )
        if not resp.is_success:
            raise IntegrationError("aws get_group_members failed", response=resp)
        raw = resp.data or []

        members = []
        for idx, membership in enumerate(raw):
            if not isinstance(membership, dict):
                logger.warning(
                    "skipped_non_dict_membership",
                    group_key=group_key,
                    membership_index=idx,
                    membership_type=type(membership).__name__,
                )
                continue

            # Extract user ID from membership
            user_id = self._extract_user_id_from_membership(membership)
            if not user_id:
                logger.warning(
                    "skipped_membership_without_user_id",
                    group_key=group_key,
                    membership=membership,
                )
                continue

            # Fetch user details
            user_data = None
            try:
                user_data = self._fetch_user_details(user_id)
            except IntegrationError as e:
                logger.warning(
                    "skipped_membership_fetch_user_failed",
                    group_key=group_key,
                    user_id=user_id,
                    error=str(e),
                )
                continue

            # Extract email from user data
            email = self._extract_email_from_user_data(user_data)
            if not email:
                logger.warning(
                    "skipped_member_without_email",
                    group_key=group_key,
                    user_id=user_id,
                    user_data_keys=list(user_data.keys()) if user_data else [],
                )
                continue

            # Build normalized member
            member_payload = {
                "email": email,
                "id": user_id,
            }
            if user_data:
                member_payload.update(user_data)

            members.append(
                as_canonical_dict(self._normalize_member_from_aws(member_payload))
            )

        logger.info(
            "get_group_members_completed",
            group_key=group_key,
            resolved_group_id=resolved_group_id,
            total_memberships=len(raw),
            valid_members=len(members),
        )

        return members

    @provider_operation(data_key="groups")
    def _list_groups_impl(self, **kwargs) -> list[dict]:
        resp = identity_store.list_groups(**kwargs)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws list_groups returned unexpected type", response=resp
            )
        if not resp.is_success:
            raise IntegrationError("aws list_groups failed", response=resp)
        raw = resp.data or []

        groups = []
        for g in raw:
            if isinstance(g, dict):
                # Normalize using the provider normalizer
                groups.append(as_canonical_dict(self._normalize_group_from_aws(g)))
        return groups

    @provider_operation(data_key="groups")
    def _list_groups_with_members_impl(self, **kwargs):
        resp = identity_store.list_groups_with_memberships(**kwargs)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws list_groups_with_members returned unexpected type", response=resp
            )
        if not resp.is_success:
            raise IntegrationError("aws list_groups_with_members failed", response=resp)
        raw = resp.data or []

        groups = []
        for g in raw:
            if isinstance(g, dict):
                # Normalize using the provider normalizer
                groups.append(as_canonical_dict(self._normalize_group_from_aws(g)))
        return groups

    @provider_operation(data_key="health")
    def _health_check_impl(self) -> HealthCheckResult:
        """Lightweight health check for AWS Identity Center connectivity.

        This performs a minimal API call to verify authentication and basic
        connectivity without consuming significant resources. Uses a simple
        list operation with maxResults=1 to minimize impact.

        Returns:
            HealthCheckResult with health status and optional details
        """
        try:
            # Get identity store ID if available (from instance attribute)
            if not self.identity_store_id:
                return self._build_health_check_result(
                    healthy=False,
                    status="degraded",
                    message="Identity store ID not configured",
                )

            # Perform minimal API call: list groups with maxResults=1
            resp = identity_store.list_groups(maxResults=1)

            if not hasattr(resp, "success"):
                return self._build_health_check_result(
                    healthy=False,
                    status="unhealthy",
                    message="AWS Identity Center API returned unexpected type",
                )

            if not resp.is_success:
                return self._build_health_check_result(
                    healthy=False,
                    status="unhealthy",
                    message="AWS Identity Center API unreachable",
                    error=str(resp),
                )

            return self._build_health_check_result(
                healthy=True,
                status="healthy",
                message="Provider is operational",
                provider_details={"identity_store_id": self.identity_store_id},
            )

        except IntegrationError as e:
            return self._build_health_check_result(
                healthy=False,
                status="unhealthy",
                message=str(e),
                provider_details={"error_code": "API_ERROR"},
            )
        except Exception as e:
            logger.error(
                "aws_health_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return self._build_health_check_result(
                healthy=False,
                status="unhealthy",
                message="Unexpected error during health check",
                error=str(e),
            )
