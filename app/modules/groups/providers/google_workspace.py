"""Google Workspace Provider"""

# Standard library
from typing import Dict, List, Optional

# Local application - core
from core.config import settings
from core.logging import get_module_logger

# Local application - integrations
from integrations.google_workspace import google_directory_next as google_directory
from integrations.google_workspace.google_directory_next import (
    ListGroupsWithMembersRequest,
)
from integrations.google_workspace.schemas import (
    Member as GoogleMember,
    Group as GoogleGroup,
)

# Local application - modules
from modules.groups.domain.errors import IntegrationError
from modules.groups.domain.models import (
    as_canonical_dict,
    NormalizedMember,
    NormalizedGroup,
)
from modules.groups.providers import register_provider
from modules.groups.providers.base import (
    PrimaryGroupProvider,
    ProviderCapabilities,
    HealthCheckResult,
    provider_operation,
    validate_member_email,
)
from infrastructure.operations import OperationResult
from infrastructure.operations.classifiers import classify_http_error


logger = get_module_logger()


@register_provider("google")
class GoogleWorkspaceProvider(PrimaryGroupProvider):
    """Google Workspace provider implementing the GroupProvider contract.

    IMPORTANT: This provider is responsible for converting all Google-specific
    schemas (GoogleMember, GoogleGroup) to canonical NormalizedMember and
    NormalizedGroup dataclasses. The provider owns all validation and conversion
    logic for its provider-specific data.
    """

    def __init__(self):
        """Initialize the provider with circuit breaker support."""
        super().__init__()
        self.requires_email_format = True
        self.domain = self._get_domain_from_settings()

    def _get_domain_from_settings(self) -> Optional[str]:
        """Get configured domain for email formatting.

        Priority:
        1. groups.group_domain from config if set
        2. Domain extracted from sre_email setting if available
        3. Return None if neither is available

        Returns:
            Domain string (e.g., "example.com") or None
        """
        # Try configured domain first
        if hasattr(settings, "groups") and hasattr(settings.groups, "group_domain"):
            configured_domain = settings.groups.group_domain
            if configured_domain:
                return configured_domain

        # Fall back to extracting domain from SRE_BOT_EMAIL setting
        sre_email = getattr(settings, "sre_email", None)
        if sre_email and "@" in sre_email:
            return sre_email.split("@", 1)[1]

        return None

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities."""
        return ProviderCapabilities(
            is_primary=True,
            supports_member_management=True,
            provides_role_info=True,
        )

    def classify_error(self, exc: Exception) -> "OperationResult":
        """Classify Google Workspace API errors into OperationResult.

        Uses infrastructure classifier to standardize error handling across
        all Google API integrations.

        Args:
            exc: Exception raised by Google API

        Returns:
            OperationResult with appropriate status and error code
        """

        return classify_http_error(exc)

    def _extract_local_part(self, email_or_identifier: Optional[str]) -> Optional[str]:
        """Extract the local part from an email-formatted identifier.

        Examples:
            "user@example.com" → "user"
            "user" → "user" (no @ found)
            None → None

        Args:
            email_or_identifier: Email address or identifier string

        Returns:
            Local part (before @) or the original string if no @ found,
            or None if input is None
        """
        if email_or_identifier and "@" in email_or_identifier:
            return email_or_identifier.split("@", 1)[0]
        return email_or_identifier

    def _normalize_group_from_google(
        self,
        group: Dict,
        members: Optional[List[Dict]] = None,
        include_raw: bool = False,
    ) -> NormalizedGroup:
        """Convert a Google group response to a NormalizedGroup with local-part ID."""
        try:
            g = GoogleGroup.model_validate(group)
        except Exception as exc:
            raise IntegrationError("google group validation failed") from exc

        email = getattr(g, "email", None)
        gid = self._extract_local_part(email)  # Use local part as ID
        name = getattr(g, "name", None) or email or gid
        description = getattr(g, "description", None)
        raw_members = members or group.get("members", [])

        normalized_members = [
            self._normalize_member_from_google(m)
            for m in raw_members
            if isinstance(m, dict)
        ]

        return NormalizedGroup(
            id=gid,
            name=name,
            description=description,
            provider="google",
            members=normalized_members,
            raw=group if include_raw else None,
        )

    def _normalize_member_from_google(
        self, member: Dict, include_raw: bool = False
    ) -> NormalizedMember:
        """Convert a Google member response to a NormalizedMember."""
        try:
            g = GoogleMember.model_validate(member)
        except Exception as exc:
            raise IntegrationError("google member validation failed") from exc

        email = getattr(g, "email", None) or getattr(g, "primaryEmail", None)
        member_id = getattr(g, "id", None)
        role = getattr(g, "role", None)
        name_field = getattr(g, "name", None)
        first_name = None
        family_name = None
        if isinstance(name_field, dict):
            first_name = name_field.get("givenName")
            family_name = name_field.get("familyName")
        elif name_field:
            first_name = getattr(name_field, "givenName", None)
            family_name = getattr(name_field, "familyName", None)

        return NormalizedMember(
            email=email,
            id=member_id,
            role=role,
            provider_member_id=member_id,
            first_name=first_name.strip() if first_name else None,
            family_name=family_name.strip() if family_name else None,
            raw=member if include_raw else None,
        )

    @provider_operation(data_key="result")
    def _add_member_impl(self, group_key: str, member_email: str) -> Dict:
        """Add a member to a group by email.

        Args:
            group_key: Google group key
            member_email: Email address of the member to add

        Returns:
            A canonical member dict (normalized NormalizedMember)
        """
        validated_email = validate_member_email(member_email)
        resp = google_directory.insert_member(group_key, validated_email)
        if hasattr(resp, "is_success") and not resp.is_success:
            raise IntegrationError("google insert_member failed", response=resp)
        if resp.data and isinstance(resp.data, dict):
            return as_canonical_dict(self._normalize_member_from_google(resp.data))
        return {}

    @provider_operation(data_key="result")
    def _remove_member_impl(self, group_key: str, member_email: str) -> Dict:
        """Remove a member from a group by email.

        Args:
            group_key: Google group key
            member_email: Email address of the member to remove

        Returns:
            A status dict confirming removal
        """
        validated_email = validate_member_email(member_email)
        resp = google_directory.delete_member(group_key, validated_email)
        if hasattr(resp, "is_success") and not resp.is_success:
            raise IntegrationError("google delete_member failed", response=resp)
        return {"status": "removed"}

    @provider_operation(data_key="members")
    def _get_group_members_impl(self, group_key: str, **kwargs) -> List[Dict]:
        """Return normalized members of a group.

        Args:
            group_key: Google group key.
            **kwargs: Additional Google API parameters.

        Returns:
            A list of canonical member dicts (normalized NormalizedMember).
        """
        resp = google_directory.list_members(group_key, **kwargs)
        if hasattr(resp, "is_success") and not resp.is_success:
            raise IntegrationError("google list_members failed", response=resp)
        raw = resp.data if hasattr(resp, "data") else resp
        return [
            as_canonical_dict(self._normalize_member_from_google(m))
            for m in (raw or [])
            if isinstance(m, dict)
        ]

    @provider_operation(data_key="groups")
    def _list_groups_impl(self, **kwargs) -> List[Dict]:
        """Return normalized groups from Google Workspace.

        This implements the abstract `_list_groups_impl` method required by
        GroupProvider/PrimaryGroupProvider so provider classes can be
        instantiated safely at decoration/import time in tests and runtime.
        """
        provider_name = kwargs.pop("provider_name", None)
        if provider_name:
            if provider_name != "google":
                kwargs["query"] = f"email:{provider_name}*"
        resp = google_directory.list_groups(**kwargs)
        if hasattr(resp, "is_success") and not resp.is_success:
            raise IntegrationError("google list_groups failed", response=resp)
        raw = resp.data if hasattr(resp, "data") else resp
        return [
            as_canonical_dict(self._normalize_group_from_google(g))
            for g in (raw or [])
            if isinstance(g, dict)
        ]

    @provider_operation(data_key="groups")
    def _list_groups_with_members_impl(
        self,
        member_email_filter: Optional[str] = None,
        member_role_filters: Optional[List[str]] = None,
        include_users_details: bool = False,
        provider_name: Optional[str] = None,
        exclude_empty_groups: bool = False,
        **kwargs,
    ) -> List[Dict]:
        """Return groups with members, optionally filtered by member criteria.

        Unified method handling all complex use cases:
        - Use case 2: member_email=john@example.ca → all groups where user is member
        - Use case 3: member_role_filters=['MANAGER','OWNER'] → groups where user is manager
        - Use case 4: include_users_details=True → enrich with full user details

        Args:
            member_email: Optional email to filter groups (include groups where this member exists).
                         If None, include all groups with members.
            member_role_filters: Optional list of roles (e.g., ['MANAGER', 'OWNER']).
                                Group is included if member has ANY of these roles.
            include_users_details: Whether to enrich members with full user details.
            provider_name: Optional provider name filter for group emails.
            exclude_empty_groups: Whether to exclude groups with no members (default False).
            **kwargs: Additional Google API parameters.

        Returns:
            List of normalized group dicts with members assembled and optionally filtered.
        """
        # Groups kwargs
        groups_kwargs = kwargs.pop("groups_kwargs", {})
        if provider_name:
            groups_kwargs["query"] = f"email:{provider_name}*"
        groups_filters = kwargs.pop("groups_filters", [])
        members_kwargs = kwargs.pop("members_kwargs", {})
        # Build member filters from parameters
        member_filters = []

        # If member_email is provided, add filter for that email
        if member_email_filter:
            member_filters.append(lambda m: m.get("email") == member_email_filter)

        # If member_role_filters provided, add filter for those roles
        if member_role_filters:
            member_filters.append(lambda m: m.get("role") in member_role_filters)

        # Prepare kwargs for integration layer
        users_kwargs = {"fields": "primaryEmail,name"} if include_users_details else {}

        # Build request for integration layer

        request = ListGroupsWithMembersRequest(
            groups_filters=groups_filters if groups_filters else None,
            member_filters=member_filters if member_filters else None,
            groups_kwargs=groups_kwargs if groups_kwargs else None,
            members_kwargs=members_kwargs if members_kwargs else None,
            users_kwargs=users_kwargs if users_kwargs else None,
            include_users_details=include_users_details,
            exclude_empty_groups=exclude_empty_groups,
        )
        logger.debug("google_list_groups_with_members_request", request=request)

        # Call integration layer with unified request
        resp = google_directory.list_groups_with_members(request)

        if hasattr(resp, "is_success") and not resp.is_success:
            raise IntegrationError(
                "google list_groups_with_members failed", response=resp
            )

        raw = resp.data if hasattr(resp, "data") else resp
        return [
            as_canonical_dict(self._normalize_group_from_google(g))
            for g in (raw or [])
            if isinstance(g, dict)
        ]

    @provider_operation(data_key="allowed")
    def _validate_permissions_impl(
        self, user_key: str, group_key: str, action: str
    ) -> bool:
        """Validate that user has permission to perform action on group.

        Checks if the user is a manager of the group. The action parameter
        is provided for future extensibility but currently only manager
        status is checked.

        Args:
            user_key: Google member key to validate
            group_key: Google group key
            action: Action type (e.g., "add_member", "remove_member")
                   Currently unused - all actions require manager role

        Returns:
            True if user is a manager and can perform the action, False otherwise

        Implementation Note:
            Delegates to _is_manager_impl for efficient manager check rather than
            listing all managers. This is more performant and achieves the same result.
        """
        # For all actions, we require manager role
        # Delegate to _is_manager_impl which efficiently checks a single member
        return self._is_manager_impl(user_key, group_key)

    @provider_operation(data_key="is_manager")
    def _is_manager_impl(self, user_key: str, group_key: str) -> bool:
        """Efficiently determine whether `user_key` is a manager of `group_key`.

        Honor runtime configuration: if the provider is not expected to expose
        role information (per settings), fall back to the base implementation
        which will try other helpers.
        """

        resp = google_directory.get_member(group_key, user_key)
        if hasattr(resp, "is_success") and not resp.is_success:
            raise IntegrationError("google get_member failed", response=resp)
        member = resp.data if hasattr(resp, "data") else resp
        if isinstance(member, dict) and "role" in member:
            return member.get("role") in ["MANAGER", "OWNER"]
        return False

    @provider_operation(data_key="health")
    def _health_check_impl(self) -> HealthCheckResult:
        """Lightweight health check for Google Workspace connectivity.

        This performs a minimal API call to verify authentication and basic
        connectivity without consuming significant quota. Uses a simple list
        operation with maxResults=1 to minimize impact.

        Returns:
            HealthCheckResult with health status and optional details
        """
        try:
            # Perform minimal API call: list groups with maxResults=1
            # Uses default customer ID from configuration
            resp = google_directory.list_groups(maxResults=1)

            if hasattr(resp, "is_success") and not resp.is_success:
                return self._build_health_check_result(
                    healthy=False,
                    status="unhealthy",
                    message="Google Workspace API unreachable",
                    error=str(resp),
                )

            return self._build_health_check_result(
                healthy=True,
                status="healthy",
                message="Provider is operational",
                provider_details={"domain": self.domain},
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
                "google_health_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return self._build_health_check_result(
                healthy=False,
                status="unhealthy",
                message="Unexpected error during health check",
                error=str(e),
            )
