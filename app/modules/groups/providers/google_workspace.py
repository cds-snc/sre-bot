"""Google Workspace Provider"""

from typing import Dict, List

from integrations.google_workspace import google_directory_next as google_directory

try:
    from integrations.google_workspace.schemas import (
        Member as GoogleMember,
        Group as GoogleGroup,
    )
except Exception as exc:
    # Fail fast with a clear error when the integration schemas can't be imported
    raise TypeError(
        "Could not import module for provider function: integrations.google_workspace.schemas"
    ) from exc
from modules.groups.providers import register_provider
from modules.groups.errors import IntegrationError
from modules.groups.schemas import (
    as_canonical_dict,
    NormalizedMember,
    NormalizedGroup,
)
from modules.groups.providers.base import GroupProvider, ProviderCapabilities


class GoogleWorkspaceProvider(GroupProvider):
    """Google Workspace provider implementing the async GroupProvider contract.
    This provider uses the existing synchronous module-level helpers via
    the sync-first methods defined in the base class.
    """

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_member_management=True)

    def _normalize_member(self, member: Dict) -> Dict:
        """Normalize a member dictionary to canonical form using Google schemas.

        Returns a canonical dict produced by `as_canonical_dict` (keeps existing
        consumers compatible).
        """
        return self._map_google_member_to_normalized(member)

    def _map_google_member_to_normalized(self, member: Dict) -> Dict:
        try:
            g = GoogleMember.model_validate(member)
        except Exception as exc:
            # Make the error explicit to callers upstream
            raise IntegrationError("google member validation failed") from exc

        # Prefer email, then primaryEmail
        email = getattr(g, "email", None) or getattr(g, "primaryEmail", None)
        member_id = getattr(g, "id", None)
        role = getattr(g, "role", None)

        # Name may be a dict or a Pydantic Name model
        first_name = None
        family_name = None
        name_field = getattr(g, "name", None)
        if isinstance(name_field, dict):
            first_name = name_field.get("givenName") or name_field.get("given")
            family_name = name_field.get("familyName") or name_field.get("family")
        else:
            # Pydantic model-like object
            try:
                first_name = getattr(name_field, "givenName", None)
                family_name = getattr(name_field, "familyName", None)
            except Exception:
                pass

        nm = NormalizedMember(
            email=email,
            id=member_id,
            role=role,
            provider_member_id=member_id,
            first_name=first_name,
            family_name=family_name,
            raw=member,
        )
        return as_canonical_dict(nm)

    def _normalize_group(self, group: Dict) -> Dict:
        """Normalize a group dictionary to canonical form using Google schemas.

        If the incoming `group` dict already contains a `members` list it will
        be mapped; otherwise the returned group's `members` will be empty and
        callers can fetch members separately.
        """
        return self._map_google_group_to_normalized(group)

    def _map_google_group_to_normalized(
        self, group: Dict, members: List[Dict] | None = None
    ) -> Dict:
        try:
            g = GoogleGroup.model_validate(group)
        except Exception as exc:
            raise IntegrationError("google group validation failed") from exc

        gid = getattr(g, "id", None) or getattr(g, "email", None)
        name = getattr(g, "name", None) or getattr(g, "email", None) or gid
        description = getattr(g, "description", None)

        # Map members if provided in call or included in the raw payload
        raw_members = members
        if raw_members is None:
            raw_members = group.get("members") if isinstance(group, dict) else None

        normalized_members = []
        if isinstance(raw_members, list):
            for m in raw_members:
                if isinstance(m, dict):
                    try:
                        normalized_members.append(
                            # keep dataclass objects for as_canonical_dict
                            NormalizedMember(**self._map_google_member_to_normalized(m))
                        )
                    except IntegrationError:
                        # skip invalid member payloads
                        continue

        ng = NormalizedGroup(
            id=gid,
            name=name,
            description=description,
            provider="google",
            members=normalized_members,
            raw=group,
        )
        return as_canonical_dict(ng)

    # ------------------------------------------------------------------
    # Sync implementations required by the sync-first GroupProvider base
    # class. These delegate to the existing module-level sync helpers so
    # providers remain sync-capable.
    # ------------------------------------------------------------------
    def get_user_managed_groups(self, user_key: str) -> List[Dict]:
        """Return canonical groups for which `user_key` is a member.

        This is the canonical synchronous implementation. Async callers
        should use the base-class async wrapper which offloads to this
        method.
        """
        resp = google_directory.list_groups(query=f"memberKey={user_key}")
        if hasattr(resp, "success"):
            if not resp.success:
                raise IntegrationError("google list_groups failed", response=resp)
            raw = resp.data or []
        else:
            raw = resp or []
        canonical = [
            # map each raw Google group dict into our canonical shape
            self._map_google_group_to_normalized(g) if isinstance(g, dict) else g
            for g in raw
        ]
        return canonical

    def add_member(self, group_key: str, member_key: str, justification: str) -> Dict:
        resp = google_directory.insert_member(group_key, member_key)
        if hasattr(resp, "success"):
            if not resp.success:
                raise IntegrationError("google insert_member failed", response=resp)
            member = {}
            if resp.data and isinstance(resp.data, dict):
                member = self._map_google_member_to_normalized(resp.data)
            return member or {}
        return resp.data

    def remove_member(
        self, group_key: str, member_key: str, justification: str
    ) -> Dict:
        resp = google_directory.delete_member(group_key, member_key)
        if hasattr(resp, "success"):
            if not resp.success:
                raise IntegrationError("google delete_member failed", response=resp)
            return {"status": "removed"}
        return resp

    def get_group_members(self, group_key: str, **kwargs) -> List[Dict]:
        resp = google_directory.list_members(group_key, **kwargs)
        if hasattr(resp, "success"):
            if not resp.success:
                raise IntegrationError("google list_members failed", response=resp)
            raw = resp.data or []
        else:
            raw = resp or []
        members = [
            self._map_google_member_to_normalized(m) if isinstance(m, dict) else m
            for m in raw
        ]
        return members

    def validate_permissions(self, user_key: str, group_key: str, action: str) -> bool:
        resp = google_directory.list_members(group_key, roles="MANAGER")
        if hasattr(resp, "success"):
            if not resp.success:
                raise IntegrationError("google list_members failed", response=resp)
            members = resp.data or []
        else:
            members = resp or []
        # normalize members and compare emails
        for m in members:
            if not isinstance(m, dict):
                continue
            normalized = self._map_google_member_to_normalized(m)
            if normalized.get("email") == user_key:
                return True
        return False


# Register provider instance
register_provider("google")(GoogleWorkspaceProvider())
