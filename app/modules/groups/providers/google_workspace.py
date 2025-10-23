"""Google Workspace Provider"""

from typing import Dict, List

from integrations.google_workspace import google_directory_next as google_directory
from integrations.google_workspace.schemas import MemberWithUser, Group
from modules.groups.providers import register_provider
from modules.groups.errors import IntegrationError
from modules.groups.schemas import as_canonical_dict, group_from_dict, member_from_dict
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
        """Normalize a member dictionary to canonical form."""
        return as_canonical_dict(member_from_dict(member, "google"))

    def _normalize_group(self, group: Dict) -> Dict:
        """Normalize a group dictionary to canonical form."""
        return as_canonical_dict(group_from_dict(group, "google"))
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
            as_canonical_dict(group_from_dict(g, "google"))
            for g in raw
            if isinstance(g, dict)
        ]
        return canonical

    def add_member(self, group_key: str, member_key: str, justification: str) -> Dict:
        resp = google_directory.insert_member(group_key, member_key)
        if hasattr(resp, "success"):
            if not resp.success:
                raise IntegrationError("google insert_member failed", response=resp)
            member = None
            if resp.data and isinstance(resp.data, dict):
                member = as_canonical_dict(member_from_dict(resp.data, "google"))
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
            as_canonical_dict(member_from_dict(m, "google"))
            for m in raw
            if isinstance(m, dict)
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
        return any(m.get("email") == user_key for m in members if isinstance(m, dict))


# Register provider instance
register_provider("google")(GoogleWorkspaceProvider())
