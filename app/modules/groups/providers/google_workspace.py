"""Google Workspace Provider"""

from typing import Dict, List, Optional

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
    opresult_wrapper,
)


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

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities."""
        return ProviderCapabilities(
            is_primary=True,
            supports_member_management=True,
            provides_role_info=True,
        )

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

    @opresult_wrapper(data_key="result")
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

    @opresult_wrapper(data_key="result")
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

    @opresult_wrapper(data_key="members")
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

    @opresult_wrapper(data_key="groups")
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

    @opresult_wrapper(data_key="groups")
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

    @opresult_wrapper(data_key="allowed")
    def validate_permissions(self, user_key: str, group_key: str, action: str) -> bool:
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

    @opresult_wrapper(data_key="groups")
    def list_groups_for_user(
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

    @opresult_wrapper(data_key="groups")
    def list_groups_managed_by_user(
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

    @opresult_wrapper(data_key="is_manager")
    def is_manager(self, user_key: str, group_key: str) -> bool:
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
