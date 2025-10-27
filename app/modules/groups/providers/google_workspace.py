"""Google Workspace Provider"""

from typing import Dict, List, Optional

from integrations.google_workspace import google_directory_next as google_directory
from integrations.google_workspace.schemas import (
    Member as GoogleMember,
    Group as GoogleGroup,
)
from modules.groups.providers import register_provider
from modules.groups.errors import IntegrationError
from modules.groups.schemas import (
    as_canonical_dict,
    NormalizedMember,
    NormalizedGroup,
)
from modules.groups.providers.base import (
    PrimaryGroupProvider,
    ProviderCapabilities,
    opresult_wrapper,
    OperationResult,
    provider_provides_role_info,
    GroupProvider,
)


@register_provider("google")
class GoogleWorkspaceProvider(PrimaryGroupProvider):
    """Google Workspace provider implementing the GroupProvider contract.

    IMPORTANT: This provider is responsible for converting all Google-specific
    schemas (GoogleMember, GoogleGroup) to canonical NormalizedMember and
    NormalizedGroup dataclasses. The provider owns all validation and conversion
    logic for its provider-specific data.
    """

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities."""
        return ProviderCapabilities(
            supports_member_management=True,
            provides_role_info=True,
        )

    def _get_local_part(self, email: Optional[str]) -> Optional[str]:
        """Extract the local part of an email address."""
        if email and "@" in email:
            return email.split("@", 1)[0]
        return email

    def _normalize_group_from_google(
        self, group: Dict, members: Optional[List[Dict]] = None
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
            raw=group,
        )

    def _normalize_member_from_google(self, member: Dict) -> NormalizedMember:
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
            first_name=first_name,
            family_name=family_name,
            raw=member,
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

    @opresult_wrapper(data_key="result")
    def add_member(
        self, group_key: str, member_data: NormalizedMember, justification: str
    ) -> Dict:
        """Add a member to a group and return the normalized member dict.

        Args:
            group_key: Google group key.
            member_data: Member identifier (str email) or dict with email/id.
            justification: Reason for adding (for audit logs).

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
    def remove_member(
        self, group_key: str, member_data: NormalizedMember, justification: str
    ) -> Dict:
        """Remove a member from a group.

        Args:
            group_key: Google group key.
            member_data: Member identifier (str email) or dict with email/id.
            justification: Reason for removal (for audit logs).

        Returns:
            A status dict confirming removal.
        """
        member_key = self._resolve_member_identifier(member_data)
        resp = google_directory.delete_member(group_key, member_key)
        if hasattr(resp, "success") and not resp.success:
            raise IntegrationError("google delete_member failed", response=resp)
        return {"status": "removed"}

    @opresult_wrapper(data_key="members")
    def get_group_members(self, group_key: str, **kwargs) -> List[Dict]:
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
    def list_groups(self, **kwargs) -> List[Dict]:
        """Return normalized groups from Google Workspace.

        This implements the abstract `list_groups` method required by
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
    def list_groups_with_members(self, **kwargs) -> List[Dict]:
        """Return normalized groups with members from Google Workspace.

        This method is not implemented for Google Workspace as it would
        require excessive API calls to fetch members for each group.
        """
        resp = google_directory.list_groups_with_members(**kwargs)
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
    def get_user_managed_groups(self, user_key: str) -> List[Dict]:
        """Return canonical groups for which `user_key` is a member.

        Args:
            user_key: A Google member key (email or ID).

        Returns:
            A list of canonical group dicts (normalized NormalizedGroup).
        """
        resp = google_directory.list_groups(query=f"memberKey={user_key}")
        if hasattr(resp, "success") and not resp.success:
            raise IntegrationError("google list_groups failed", response=resp)
        raw = resp.data if hasattr(resp, "data") else resp
        return [
            as_canonical_dict(self._normalize_group_from_google(g))
            for g in (raw or [])
            if isinstance(g, dict)
        ]

    def is_manager(self, user_key: str, group_key: str) -> OperationResult:
        """Efficiently determine whether `user_key` is a manager of `group_key`.

        Honor runtime configuration: if the provider is not expected to expose
        role information (per settings), fall back to the base implementation
        which will try other helpers.
        """
        # Respect configuration-driven capability flag. The explicit call to
        # GroupProvider.is_manager ensures we invoke the concrete base
        # implementation (PrimaryGroupProvider declares is_manager as an
        # abstractmethod and does not provide a fallback implementation).
        if not provider_provides_role_info("google"):
            return GroupProvider.is_manager(self, user_key, group_key)

        try:
            resp = google_directory.list_members(group_key, roles="MANAGER")
            if hasattr(resp, "success") and not resp.success:
                raise IntegrationError("google list_members failed", response=resp)
            members = resp.data if hasattr(resp, "data") else resp
            for m in members or []:
                if isinstance(m, dict):
                    normalized = self._normalize_member_from_google(m)
                    if normalized.email == user_key or normalized.id == user_key:
                        return OperationResult.success(
                            data={"allowed": True, "role": "MANAGER"}
                        )
            return OperationResult.success(data={"allowed": False})
        except IntegrationError:
            # Integration-specific errors should be surfaced as transient
            return OperationResult.transient_error("google integration error")
        except Exception as e:
            return OperationResult.transient_error(str(e))
