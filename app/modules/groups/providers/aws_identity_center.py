from typing import Any, Dict, List, Optional

from botocore.exceptions import BotoCoreError, ClientError
from core.logging import get_module_logger
from integrations.aws import identity_store_next as identity_store
from integrations.aws.schemas import Group as AwsGroup
from integrations.aws.schemas import GroupMembership as AwsGroupMembership
from integrations.aws.schemas import User as AwsUser
from modules.groups.errors import IntegrationError
from modules.groups.models import NormalizedGroup, NormalizedMember, as_canonical_dict
from modules.groups.providers import register_provider
from modules.groups.providers.base import (
    GroupProvider,
    OperationResult,
    OperationStatus,
    ProviderCapabilities,
    opresult_wrapper,
)

logger = get_module_logger()


@register_provider("aws")
class AwsIdentityCenterProvider(GroupProvider):
    """AWS Identity Center provider implementing the GroupProvider contract.

    Third party provider: AWS Identity Center (successor to AWS SSO)

    Supports:
    - User creation
    - User deletion
    - Membership creation
    - Membership deletion
    - Fetching groups

    IMPORTANT: This provider is responsible for converting all AWS-specific
    schemas (AwsUser, AwsGroup) to canonical NormalizedMember and NormalizedGroup
    dataclasses. The provider owns all validation and conversion logic for its
    provider-specific data.
    """

    def __init__(self):
        """Initialize the provider with circuit breaker support."""
        super().__init__()

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities."""
        return ProviderCapabilities(supports_member_management=True)

    def classify_error(self, exc: Exception) -> "OperationResult":
        """Classify AWS Identity Center API errors into OperationResult.

        Handles:
        - ThrottlingException (rate limiting) with retry_after
        - AccessDeniedException (permission denied) as permanent
        - ResourceNotFoundException (not found) as permanent
        - Validation errors as permanent
        - Connection/timeout errors as transient
        - Other errors as transient by default

        Args:
            exc: Exception raised by AWS API

        Returns:
            OperationResult with appropriate status and error code
        """

        if isinstance(exc, ClientError):
            error_code = exc.response.get("Error", {}).get("Code", "Unknown")

            # Rate limiting: ThrottlingException
            if error_code == "ThrottlingException":
                retry_after = 60  # Default retry after 60 seconds
                return OperationResult.error(
                    OperationStatus.TRANSIENT_ERROR,
                    "AWS API throttled",
                    error_code="RATE_LIMITED",
                    retry_after=retry_after,
                )

            # Permission denied: AccessDeniedException
            if error_code == "AccessDeniedException":
                return OperationResult.permanent_error(
                    "AWS API access denied",
                    error_code="FORBIDDEN",
                )

            # Resource not found: ResourceNotFoundException
            if error_code == "ResourceNotFoundException":
                return OperationResult.error(
                    OperationStatus.NOT_FOUND,
                    "AWS resource not found",
                    error_code="NOT_FOUND",
                )

            # Validation errors (bad input)
            if error_code in (
                "ValidationException",
                "InvalidParameterException",
                "BadRequestException",
            ):
                return OperationResult.permanent_error(
                    f"AWS validation error: {error_code}",
                    error_code="INVALID_REQUEST",
                )

            # Other client errors: treat as transient by default
            return OperationResult.transient_error(
                f"AWS error ({error_code}): {str(exc)}"
            )

        # BotoCoreError: connection, timeout, parsing errors
        if isinstance(exc, BotoCoreError):
            return OperationResult.transient_error(f"AWS connection error: {str(exc)}")

        # Connection/timeout errors
        if isinstance(exc, (TimeoutError, ConnectionError)):
            return OperationResult.transient_error(
                f"AWS connection timeout: {str(exc)}"
            )

        # Default: treat as transient error
        return OperationResult.transient_error(str(exc))

    # ------------------------------------------------------------------
    # Instance helpers (migrated from module-level into the provider)
    # ------------------------------------------------------------------
    def _extract_id_from_resp(self, resp: Any, id_keys: List[str]) -> Optional[str]:
        if resp is None:
            return None
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws identity_store returned unexpected type", response=resp
            )
        if not resp.success:
            return None
        data = resp.data

        if isinstance(data, str):
            return data

        if isinstance(data, dict):
            for k in id_keys:
                if k in data and data[k]:
                    return data[k]
            if "MemberId" in data and isinstance(data["MemberId"], dict):
                return data["MemberId"].get("UserId") or data["MemberId"].get("Id")
            if "UserId" in data:
                return data.get("UserId")
        return None

    def _ensure_user_id_from_email(self, email: str) -> str:
        if not hasattr(identity_store, "get_user_by_username"):
            raise IntegrationError(
                "aws identity_store missing get_user_by_username", response=None
            )
        resp = identity_store.get_user_by_username(email)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws get_user_by_username returned unexpected type", response=resp
            )
        if not resp.success:
            raise IntegrationError("aws resolve user id failed", response=resp)
        uid = self._extract_id_from_resp(resp, ["UserId", "Id"])
        if not uid:
            raise ValueError(f"could not resolve user id for email={email}")
        return uid

    def _resolve_group_id(self, group_key: str) -> str:
        """Resolve a group identifier to AWS GroupId (UUID format).

        AWS Identity Center APIs accept either:
        - GroupId: UUID format (e.g., 906abc12-d3e4-5678-90ab-cdef12345678)
        - DisplayName: canonical name (e.g., digitaltransformationoffice-ai-staging-admin)

        This method checks if the input is already a UUID. If not, it calls
        get_group_by_name to resolve the display name to a GroupId.

        Args:
            group_key: Either a UUID GroupId or a display name

        Returns:
            AWS GroupId in UUID format

        Raises:
            IntegrationError: If group cannot be resolved
        """
        import re

        # AWS GroupId pattern: ([0-9a-f]{10}-|)[A-Fa-f0-9]{8}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}-[A-Fa-f0-9]{12}
        # Simplified check: if it looks like a UUID, assume it's already a GroupId
        uuid_pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        if re.match(uuid_pattern, group_key.strip()):
            return group_key.strip()

        # Not a UUID, treat as display name and resolve
        if not hasattr(identity_store, "get_group_by_name"):
            raise IntegrationError(
                "aws identity_store missing get_group_by_name", response=None
            )

        resp = identity_store.get_group_by_name(group_key)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws get_group_by_name returned unexpected type", response=resp
            )
        if not resp.success:
            raise IntegrationError(
                f"aws resolve group id failed for display name: {group_key}",
                response=resp,
            )

        # Extract GroupId from response
        group_id = self._extract_id_from_resp(resp, ["GroupId", "Id"])
        if not group_id:
            raise ValueError(f"could not resolve group id for display name={group_key}")

        return group_id

    def _resolve_membership_id(self, group_key: str, user_id: str) -> str:
        """Resolve the membership ID for a user in a group.
            AWS Identity Center APIs uses memberships to associate users to groups.

        Args:
            group_key: AWS group key (UUID or display name).
            user_id: AWS user ID.
        """
        if not hasattr(identity_store, "get_group_membership_id"):
            raise IntegrationError(
                "aws identity_store missing get_group_membership_id", response=None
            )
        resp = identity_store.get_group_membership_id(group_key, user_id)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws resolve membership id returned unexpected type", response=resp
            )
        if not resp.success:
            raise IntegrationError("aws resolve membership id failed", response=resp)
        mid = self._extract_id_from_resp(resp, ["MembershipId", "MembershipId"])
        if not mid:
            raise ValueError(
                f"could not resolve membership id for group={group_key} user={user_id}"
            )
        return mid

    def _fetch_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        if not hasattr(identity_store, "get_user"):
            raise IntegrationError("aws identity_store missing get_user", response=None)
        resp = identity_store.get_user(user_id)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws get_user returned unexpected type", response=resp
            )
        if not resp.success:
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

    def _resolve_member_identifier(self, member_data: dict | str) -> str:
        """Convert member_data input to an AWS-compatible identifier.

        This provider method handles the flexibility of accepting str or dict,
        but validates and converts to what AWS expects.

        Args:
            member_data: Either a string email or a dict with email/id keys.

        Returns:
            An AWS member identifier (email string).

        Raises:
            ValueError: If the input cannot be resolved to a member identifier.
        """
        if isinstance(member_data, str):
            if not member_data.strip():
                raise ValueError("Member identifier string cannot be empty")
            return member_data.strip()

        if isinstance(member_data, dict):
            email = member_data.get("email")
            if not email:
                raise ValueError("Member dict must contain 'email' field")
            return email

        raise TypeError(
            f"member_data must be str or dict; got {type(member_data).__name__}"
        )

    @opresult_wrapper(data_key="result")
    def _add_member_impl(
        self, group_key: str, member_data: NormalizedMember | dict | str
    ) -> dict:
        """Add a member to a group and return the normalized member dict.

        Args:
            group_key: AWS group key (UUID or display name).
            member_data: Member identifier (NormalizedMember, str email, or dict with email).

        Returns:
            A canonical member dict (normalized NormalizedMember).
        """
        # Handle NormalizedMember input (from orchestration propagation)
        if isinstance(member_data, NormalizedMember):
            email = getattr(member_data, "email", None)
            if not email:
                raise ValueError("NormalizedMember must include email")
            member_data = {"email": email}

        if not isinstance(member_data, dict):
            raise ValueError("member_data must be a dict containing at least 'email'")
        email = member_data.get("email")
        if not email:
            raise ValueError("member_data.email is required")

        # Resolve group_key to UUID format
        resolved_group_id = self._resolve_group_id(group_key)

        user_id = self._ensure_user_id_from_email(email)
        if not hasattr(identity_store, "create_group_membership"):
            raise IntegrationError(
                "aws identity_store missing create_group_membership", response=None
            )
        resp = identity_store.create_group_membership(resolved_group_id, user_id)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws create_group_membership returned unexpected type", response=resp
            )
        if not resp.success:
            raise IntegrationError("aws add_user_to_group failed", response=resp)
        try:
            user_data = self._fetch_user_details(user_id)
        except IntegrationError:
            user_data = None
        member_payload = {"email": email, "id": user_id}
        if user_data:
            member_payload.update({"Name": user_data.get("Name") or {}})
        return as_canonical_dict(self._normalize_member_from_aws(member_payload))

    @opresult_wrapper(data_key="result")
    def _remove_member_impl(
        self, group_key: str, member_data: NormalizedMember | dict | str
    ) -> dict:
        """Remove a member from a group and return the normalized member dict.

        Args:
            group_key: AWS group key (UUID or display name).
            member_data: Member identifier (NormalizedMember, str email, or dict with email).

        Returns:
            A canonical member dict (normalized NormalizedMember).
        """
        # Handle NormalizedMember input (from orchestration propagation)
        if isinstance(member_data, NormalizedMember):
            email = getattr(member_data, "email", None)
            if not email:
                raise ValueError("NormalizedMember must include email")
            member_data = {"email": email}

        if not isinstance(member_data, dict):
            raise ValueError("member_data must be a dict containing at least 'email'")
        email = member_data.get("email")
        if not email:
            raise ValueError("member_data.email is required")

        # Resolve group_key to UUID format
        resolved_group_id = self._resolve_group_id(group_key)

        user_id = self._ensure_user_id_from_email(email)
        membership_id = self._resolve_membership_id(resolved_group_id, user_id)
        if not hasattr(identity_store, "delete_group_membership"):
            raise IntegrationError(
                "aws identity_store missing delete_group_membership", response=None
            )
        resp = identity_store.delete_group_membership(membership_id)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws delete_group_membership returned unexpected type", response=resp
            )
        if not resp.success:
            raise IntegrationError("aws remove_user_from_group failed", response=resp)
        try:
            user_data = self._fetch_user_details(user_id)
        except IntegrationError:
            user_data = None
        member_payload = {"email": email, "id": user_id}
        if user_data:
            member_payload.update({"Name": user_data.get("Name") or {}})
        return as_canonical_dict(self._normalize_member_from_aws(member_payload))

    @opresult_wrapper(data_key="members")
    def _get_group_members_impl(self, group_key: str, **kwargs) -> list[dict]:
        """AWS returns the list of canonical memberships, not the user details."""
        # Resolve group_key to UUID format for consistency
        resolved_group_id = self._resolve_group_id(group_key)

        if not hasattr(identity_store, "list_group_memberships"):
            raise IntegrationError(
                "aws identity_store missing list_group_memberships", response=None
            )
        resp = identity_store.list_group_memberships(resolved_group_id)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws list_group_memberships returned unexpected type", response=resp
            )
        if not resp.success:
            raise IntegrationError("aws get_group_members failed", response=resp)
        raw = resp.data or []

        members = []
        for m in raw:
            if not isinstance(m, dict):
                continue
            member_id = None
            # TODO: FIX the AWS SDK does not return the UserId, a subsequent
            # call to get_user_details will need to handle this case.
            if "MemberId" in m and isinstance(m["MemberId"], dict):
                member_id = m["MemberId"].get("UserId")
            user_data = None
            if member_id:
                try:
                    user_data = self._fetch_user_details(member_id)
                except IntegrationError:
                    user_data = None
            member_payload = {}
            if user_data:
                member_payload.update(user_data)
                member_payload["email"] = (
                    member_payload.get("Emails", [{}])[0].get("Value")
                    if isinstance(member_payload.get("Emails"), list)
                    else member_payload.get("email")
                )
                member_payload["id"] = member_payload.get("UserId") or member_id
                members.append(
                    as_canonical_dict(self._normalize_member_from_aws(member_payload))
                )
                continue
            member_payload["id"] = member_id
            member_payload["email"] = None
            members.append(
                as_canonical_dict(self._normalize_member_from_aws(member_payload))
            )
        return members

    @opresult_wrapper(data_key="groups")
    def _list_groups_impl(self, **kwargs) -> list[dict]:
        if not hasattr(identity_store, "list_groups"):
            raise IntegrationError(
                "aws identity_store missing list_groups", response=None
            )
        resp = identity_store.list_groups(**kwargs)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws list_groups returned unexpected type", response=resp
            )
        if not resp.success:
            raise IntegrationError("aws list_groups failed", response=resp)
        raw = resp.data or []

        groups = []
        for g in raw:
            if isinstance(g, dict):
                # Normalize using the provider normalizer
                groups.append(as_canonical_dict(self._normalize_group_from_aws(g)))
        return groups

    @opresult_wrapper(data_key="groups")
    def _list_groups_with_members_impl(self, **kwargs):
        resp = identity_store.list_groups_with_memberships(**kwargs)
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws list_groups_with_members returned unexpected type", response=resp
            )
        if not resp.success:
            raise IntegrationError("aws list_groups_with_members failed", response=resp)
        raw = resp.data or []

        groups = []
        for g in raw:
            if isinstance(g, dict):
                # Normalize using the provider normalizer
                groups.append(as_canonical_dict(self._normalize_group_from_aws(g)))
        return groups

    @opresult_wrapper(data_key="health")
    def _health_check_impl(self) -> dict:
        """Lightweight health check for AWS Identity Center connectivity.

        This performs a minimal API call to verify authentication and basic
        connectivity without consuming significant resources. Uses a simple
        list operation with maxResults=1 to minimize impact.

        Returns:
            Dictionary with 'status' and optional 'identity_store_id' field
        """
        try:
            # Get identity store ID if available (from instance attribute)
            identity_store_id = getattr(self, "identity_store_id", None)
            if not identity_store_id:
                return {
                    "status": "degraded",
                    "message": "Identity store ID not configured",
                }

            # Perform minimal API call: list groups with maxResults=1
            resp = identity_store.list_groups(maxResults=1)

            if not hasattr(resp, "success"):
                return {
                    "status": "unhealthy",
                    "message": "AWS Identity Center API returned unexpected type",
                }

            if not resp.success:
                return {
                    "status": "unhealthy",
                    "message": "AWS Identity Center API unreachable",
                    "error": str(resp),
                }

            return {
                "status": "healthy",
                "identity_store_id": identity_store_id,
                "message": "Provider is operational",
            }

        except IntegrationError as e:
            return {"status": "unhealthy", "message": str(e), "error_code": "API_ERROR"}
        except Exception as e:
            logger.error(
                "aws_health_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return {
                "status": "unhealthy",
                "message": "Unexpected error during health check",
                "error": str(e),
            }
