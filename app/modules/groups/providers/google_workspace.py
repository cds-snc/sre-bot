"""Google Workspace Provider"""

import os
from typing import Dict, List, Optional

from core.logging import get_module_logger
from integrations.google_workspace import google_directory_next as google_directory
from integrations.google_workspace.schemas import (
    Member as GoogleMember,
    Group as GoogleGroup,
)
from modules.groups.providers import register_provider
from modules.groups.errors import IntegrationError
from modules.groups.models import (
    as_canonical_dict,
    NormalizedMember,
    NormalizedGroup,
)
from modules.groups.providers.base import (
    PrimaryGroupProvider,
    ProviderCapabilities,
    OperationResult,
    OperationStatus,
    provider_operation,
)

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
        self.domain = None

    def _set_domain_from_config(self) -> None:
        """Extract domain from config or SRE_BOT_EMAIL environment variable.

        Priority:
        1. groups.group_domain from config if set
        2. Domain extracted from SRE_BOT_EMAIL if available
        3. Remain None if neither is available
        """
        from core.config import settings

        # Try configured domain first
        if hasattr(settings, "groups") and hasattr(settings.groups, "group_domain"):
            configured_domain = settings.groups.group_domain
            if configured_domain:
                self.domain = configured_domain
                return

        # Fall back to extracting domain from SRE_BOT_EMAIL
        sre_email = getattr(settings, "sre_email", None) or os.environ.get(
            "SRE_BOT_EMAIL"
        )
        if sre_email and "@" in sre_email:
            self.domain = sre_email.split("@", 1)[1]

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

        Handles:
        - 429 (rate limit) with retry_after from headers
        - 401/403 (auth errors) as permanent
        - 404 (not found) as permanent
        - 5xx (server errors) as transient
        - Connection/timeout errors as transient

        Args:
            exc: Exception raised by Google API

        Returns:
            OperationResult with appropriate status and error code
        """
        from googleapiclient.errors import HttpError

        if isinstance(exc, HttpError):
            status_code = exc.resp.status if hasattr(exc, "resp") else None

            # Rate limiting: 429 Too Many Requests
            if status_code == 429:
                retry_after = None
                if hasattr(exc, "resp") and hasattr(exc.resp, "get"):
                    retry_after = int(exc.resp.get("retry-after", 60))
                return OperationResult.error(
                    OperationStatus.TRANSIENT_ERROR,
                    "Google API rate limited",
                    error_code="RATE_LIMITED",
                    retry_after=retry_after,
                )

            # Authentication errors: 401 Unauthorized
            if status_code == 401:
                return OperationResult.permanent_error(
                    "Google API authentication failed",
                    error_code="UNAUTHORIZED",
                )

            # Authorization errors: 403 Forbidden
            if status_code == 403:
                return OperationResult.permanent_error(
                    "Google API authorization denied",
                    error_code="FORBIDDEN",
                )

            # Not found: 404
            if status_code == 404:
                return OperationResult.error(
                    OperationStatus.NOT_FOUND,
                    "Google resource not found",
                    error_code="NOT_FOUND",
                )

            # Server errors: 5xx
            if status_code and 500 <= status_code < 600:
                return OperationResult.transient_error(
                    f"Google API server error ({status_code})"
                )

            # Other HTTP errors
            return OperationResult.transient_error(
                f"Google API error ({status_code}): {str(exc)}"
            )

        # Connection/timeout errors: treat as transient
        if isinstance(exc, (TimeoutError, ConnectionError)):
            return OperationResult.transient_error(
                f"Google API connection error: {str(exc)}"
            )

        # Default: treat as transient error
        return OperationResult.transient_error(str(exc))

    def _get_local_part(self, email: Optional[str]) -> Optional[str]:
        """Extract the local part of an email address."""
        if email and "@" in email:
            return email.split("@", 1)[0]
        return email

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
        gid = self._get_local_part(email)  # Use local part as ID
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

    def _resolve_member_identifier(
        self, member_data: dict | str | NormalizedMember
    ) -> str:
        """Convert member_data input to a Google-compatible identifier.

        This provider method handles the flexibility of accepting str or dict,
        but validates and converts to what Google expects.

        Args:
            member_data: Either a string email or a dict with email/id keys.

        Returns:
            A Google member key (email or ID string).

        Raises:
            ValueError: If the input cannot be resolved to a member identifier.
        """
        # Accept NormalizedMember instances, dicts, or raw string identifiers
        if isinstance(member_data, NormalizedMember):
            email = getattr(member_data, "email", None)
            member_id = getattr(member_data, "id", None)
            identifier = email or member_id
            if not identifier:
                raise ValueError("NormalizedMember must include email or id")
            return identifier

        if isinstance(member_data, str):
            if not member_data.strip():
                raise ValueError("Member identifier string cannot be empty")
            return member_data.strip()

        if isinstance(member_data, dict):
            email = member_data.get("email") or member_data.get("primaryEmail")
            member_id = member_data.get("id")
            identifier = email or member_id
            if not identifier:
                raise ValueError("Member dict must contain 'email' or 'id' field")
            return identifier

        raise TypeError(
            f"member_data must be str or dict; got {type(member_data).__name__}"
        )

    def _list_groups_with_members_for_user(
        self, user_key: str, provider_name: Optional[str], **kwargs
    ) -> List[Dict]:
        """List groups with members for a user (not implemented for Google)."""
        users_kwargs = {"fields": "primaryEmail,name"}
        groups_kwargs = {"query": "memberKey=" + user_key}
        if provider_name and provider_name != "google":
            groups_filters = [
                lambda g: isinstance(g, dict)
                and g.get("email", "").lower().startswith(provider_name.lower())
            ]
            resp = google_directory.list_groups_with_members(
                groups_filters=groups_filters,
                groups_kwargs=groups_kwargs,
                users_kwargs=users_kwargs,
                **kwargs,
            )
        else:
            resp = google_directory.list_groups_with_members(
                groups_kwargs=groups_kwargs, users_kwargs=users_kwargs, **kwargs
            )
        if hasattr(resp, "success") and not resp.success:
            raise IntegrationError(
                "google list_groups_with_members failed", response=resp
            )
        raw = resp.data if hasattr(resp, "data") else resp
        return [
            as_canonical_dict(self._normalize_group_from_google(g))
            for g in (raw or [])
            if isinstance(g, dict)
        ]

    @provider_operation(data_key="result")
    def _add_member_impl(self, group_key: str, member_data: NormalizedMember) -> Dict:
        """Add a member to a group and return the normalized member dict.

        Args:
            group_key: Google group key.
            member_data: Member identifier (str email) or dict with email/id.

        Returns:
            A canonical member dict (normalized NormalizedMember).
        """
        member_key = self._resolve_member_identifier(member_data)
        resp = google_directory.insert_member(group_key, member_key)
        if hasattr(resp, "success") and not resp.success:
            raise IntegrationError("google insert_member failed", response=resp)
        if resp.data and isinstance(resp.data, dict):
            return as_canonical_dict(self._normalize_member_from_google(resp.data))
        return {}

    @provider_operation(data_key="result")
    def _remove_member_impl(
        self, group_key: str, member_data: NormalizedMember
    ) -> Dict:
        """Remove a member from a group.

        Args:
            group_key: Google group key.
            member_data: Member identifier (str email) or dict with email/id.

        Returns:
            A status dict confirming removal.
        """
        member_key = self._resolve_member_identifier(member_data)
        resp = google_directory.delete_member(group_key, member_key)
        if hasattr(resp, "success") and not resp.success:
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
        if hasattr(resp, "success") and not resp.success:
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
        resp = google_directory.list_groups(**kwargs)
        if hasattr(resp, "success") and not resp.success:
            raise IntegrationError("google list_groups failed", response=resp)
        raw = resp.data if hasattr(resp, "data") else resp
        return [
            as_canonical_dict(self._normalize_group_from_google(g))
            for g in (raw or [])
            if isinstance(g, dict)
        ]

    @provider_operation(data_key="groups")
    def _list_groups_with_members_impl(self, **kwargs) -> List[Dict]:
        """Return normalized groups with members from Google Workspace.

        This method is not implemented for Google Workspace as it would
        require excessive API calls to fetch members for each group.
        """
        users_kwargs = {"fields": "primaryEmail,name"}
        resp = google_directory.list_groups_with_members(
            users_kwargs=users_kwargs, **kwargs
        )
        if hasattr(resp, "success") and not resp.success:
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
        """Return True if user is a MANAGER of the group, else False.

        Args:
            user_key: Google member key to validate.
            group_key: Google group key.
            action: Action type (currently unused but part of the contract).

        Returns:
            True if user is a manager, False otherwise.
        """
        resp = google_directory.list_members(group_key, roles="MANAGER")
        if hasattr(resp, "success") and not resp.success:
            raise IntegrationError("google list_members failed", response=resp)
        members = resp.data if hasattr(resp, "data") else resp
        for m in members or []:
            if isinstance(m, dict):
                normalized = self._normalize_member_from_google(m)
                if normalized.email == user_key or normalized.id == user_key:
                    return True
        return False

    @provider_operation(data_key="groups")
    def _list_groups_for_user_impl(
        self, user_key: str, provider_name: Optional[str], **kwargs
    ) -> List[Dict]:
        """Return canonical groups for which `user_key` is a member.

        Args:
            user_key: A Google member key (email or ID).
            provider_name: Optional provider name filter.

        Returns:
            A list of canonical group dicts (normalized NormalizedGroup).
        """
        users_kwargs = {"fields": "primaryEmail,name"}
        groups_kwargs = {"query": "memberKey=" + user_key}
        if provider_name and provider_name != "google":
            groups_filters = [
                lambda g: isinstance(g, dict)
                and g.get("email", "").lower().startswith(provider_name.lower())
            ]
            resp = google_directory.list_groups_with_members(
                groups_filters=groups_filters,
                groups_kwargs=groups_kwargs,
                users_kwargs=users_kwargs,
                **kwargs,
            )
        else:
            resp = google_directory.list_groups_with_members(
                groups_kwargs=groups_kwargs, users_kwargs=users_kwargs, **kwargs
            )
        if hasattr(resp, "success") and not resp.success:
            raise IntegrationError(
                "google list_groups_with_members failed", response=resp
            )
        raw = resp.data if hasattr(resp, "data") else resp
        return [
            as_canonical_dict(self._normalize_group_from_google(g))
            for g in (raw or [])
            if isinstance(g, dict)
        ]

    @provider_operation(data_key="groups")
    def _list_groups_managed_by_user_impl(
        self, user_key: str, provider_name: Optional[str], **kwargs
    ) -> List[Dict]:
        """Return groups keys where the user is a MANAGER or OWNER.

        Args:
            user_key: A Google member key (email or ID).

        Returns:
            A list of group keys (emails) where the user is a MANAGER or OWNER.
        """
        groups_list = self._list_groups_with_members_for_user(
            user_key, provider_name=provider_name, **kwargs
        )
        managed_groups: List[Dict] = []
        if isinstance(groups_list, list):
            for group in groups_list:
                if not group or not isinstance(group, dict):
                    continue
                if isinstance(group, dict):
                    role = group.get("role")
                    if role in ("MANAGER", "OWNER"):
                        managed_groups.append(group)

        return managed_groups

    @provider_operation(data_key="is_manager")
    def _is_manager_impl(self, user_key: str, group_key: str) -> bool:
        """Efficiently determine whether `user_key` is a manager of `group_key`.

        Honor runtime configuration: if the provider is not expected to expose
        role information (per settings), fall back to the base implementation
        which will try other helpers.
        """

        resp = google_directory.get_member(group_key, user_key)
        if hasattr(resp, "success") and not resp.success:
            raise IntegrationError("google get_member failed", response=resp)
        member = resp.data if hasattr(resp, "data") else resp
        if isinstance(member, dict) and "role" in member:
            return member.get("role") in ["MANAGER", "OWNER"]
        return False

    @provider_operation(data_key="health")
    def _health_check_impl(self) -> Dict:
        """Lightweight health check for Google Workspace connectivity.

        This performs a minimal API call to verify authentication and basic
        connectivity without consuming significant quota. Uses a simple list
        operation with maxResults=1 to minimize impact.

        Returns:
            Dictionary with 'status' field
        """
        try:
            # Perform minimal API call: list groups with maxResults=1
            # Uses default customer ID from configuration
            resp = google_directory.list_groups(maxResults=1)

            if hasattr(resp, "success") and not resp.success:
                return {
                    "status": "unhealthy",
                    "message": "Google Workspace API unreachable",
                    "error": str(resp),
                }

            return {
                "status": "healthy",
                "domain": self.domain,
                "message": "Provider is operational",
            }

        except IntegrationError as e:
            return {"status": "unhealthy", "message": str(e), "error_code": "API_ERROR"}
        except Exception as e:
            logger.error(
                "google_health_check_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return {
                "status": "unhealthy",
                "message": "Unexpected error during health check",
                "error": str(e),
            }
