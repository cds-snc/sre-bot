from typing import Dict, List, Optional, Any

from integrations.aws import identity_store_next as identity_store

try:
    from integrations.aws.schemas import User as AwsUser, Group as AwsGroup
except Exception as exc:
    raise TypeError(
        "Could not import module for provider function: integrations.aws.schemas"
    ) from exc
from modules.groups.errors import IntegrationError
from modules.groups.providers import register_provider
from modules.groups.schemas import (
    as_canonical_dict,
    NormalizedMember,
    NormalizedGroup,
)
from modules.groups.providers.base import (
    GroupProvider,
    ProviderCapabilities,
)


class AwsIdentityCenterProvider(GroupProvider):
    """AWS Identity Center provider implementing the GroupProvider contract."""

    def get_user_managed_groups(self, user_key: str) -> list[dict]:
        return self.get_user_managed_groups_sync(user_key)

    def add_member(
        self, group_key: str, member: dict | str, justification: str
    ) -> dict:
        member_dict = {"email": member} if isinstance(member, str) else member
        return self.add_member_sync(group_key, member_dict, justification)

    def remove_member(
        self, group_key: str, member: dict | str, justification: str
    ) -> dict:
        member_dict = {"email": member} if isinstance(member, str) else member
        return self.remove_member_sync(group_key, member_dict, justification)

    def get_group_members(self, group_key: str, **kwargs) -> list[dict]:
        return self.get_group_members_sync(group_key, **kwargs)

    def validate_permissions(self, user_key: str, group_key: str, action: str) -> bool:
        return self.validate_permissions_sync(user_key, group_key, action)

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_member_management=True)

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

    def _resolve_membership_id(self, group_key: str, user_id: str) -> str:
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

    def _map_aws_member_to_normalized(self, member: dict) -> dict:
        try:
            u = AwsUser.model_validate(member)
        except Exception as exc:
            raise IntegrationError("aws member validation failed") from exc

        email = None
        emails = getattr(u, "Emails", None)
        if isinstance(emails, list) and emails:
            first = emails[0]
            email = (
                getattr(first, "Value", None)
                if hasattr(first, "Value")
                else first.get("Value") if isinstance(first, dict) else None
            )
        email = email or getattr(u, "UserName", None) or member.get("email")

        member_id = getattr(u, "UserId", None)

        first_name = None
        family_name = None
        name = getattr(u, "Name", None)
        if name:
            first_name = getattr(name, "GivenName", None)
            family_name = getattr(name, "FamilyName", None)

        nm = NormalizedMember(
            email=email,
            id=member_id,
            role=None,
            provider_member_id=member_id,
            first_name=first_name,
            family_name=family_name,
            raw=member,
        )
        return as_canonical_dict(nm)

    def _map_aws_group_to_normalized(
        self, group: dict, members: List[Dict] | None = None
    ) -> dict:
        try:
            g = AwsGroup.model_validate(group)
        except Exception as exc:
            raise IntegrationError("aws group validation failed") from exc

        gid = getattr(g, "GroupId", None)
        name = getattr(g, "DisplayName", None) or gid
        description = getattr(g, "Description", None)

        raw_members = members
        if raw_members is None:
            raw_members = group.get("members") if isinstance(group, dict) else None

        normalized_members = []
        if isinstance(raw_members, list):
            for m in raw_members:
                if isinstance(m, dict):
                    # Enforce strict member normalization: let validation errors
                    # propagate instead of silently skipping malformed members.
                    normalized_members.append(
                        NormalizedMember(**self._map_aws_member_to_normalized(m))
                    )

        ng = NormalizedGroup(
            id=gid,
            name=name,
            description=description,
            provider="aws",
            members=normalized_members,
            raw=group,
        )
        return as_canonical_dict(ng)

    def _add_user(self, user_key: str, first_name: str, family_name: str):
        if not hasattr(identity_store, "create_user"):
            raise IntegrationError(
                "aws identity_store missing create_user", response=None
            )
        resp = identity_store.create_user(
            user_key, first_name=first_name, family_name=family_name
        )
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws create_user returned unexpected type", response=resp
            )
        if not resp.success:
            raise IntegrationError("aws create_user failed", response=resp)
        return self._map_aws_member_to_normalized(resp.data)

    def _get_user_managed_groups(self, member: Dict | str) -> List[Dict]:
        if isinstance(member, str):
            email = member
        elif isinstance(member, dict):
            email = member.get("email")
        else:
            email = None

        if not email:
            raise ValueError("member.email is required")
        # Resolve the user's id and use the memberships listing path.
        # Backward-compat branch that accepted a direct get_groups_for_user
        # call is removed: integrations must support member id resolution
        # and return IntegrationResponse-like objects.
        user_id = self._ensure_user_id_from_email(email)
        if not hasattr(identity_store, "list_group_memberships_for_member"):
            raise IntegrationError(
                "aws identity_store missing list_group_memberships_for_member",
                response=None,
            )
        resp = identity_store.list_group_memberships_for_member(user_id, role="MANAGER")
        if not hasattr(resp, "success"):
            raise IntegrationError(
                "aws list_group_memberships_for_member returned unexpected type",
                response=resp,
            )
        if not resp.success:
            raise IntegrationError(
                "aws list_group_memberships_for_member failed", response=resp
            )
        raw = resp.data or []

        groups = []
        for m in raw:
            if not isinstance(m, dict):
                continue
            group_payload = m.get("Group") or m.get("group")
            # Only accept a full Group payload (dict). If the membership entry
            # lacks a group object (e.g., only contains an id), skip it — the
            # integration should provide sufficient payloads in the IntegrationResponse.
            if isinstance(group_payload, dict):
                groups.append(self._map_aws_group_to_normalized(group_payload))
        return groups

    def _add_member(self, group_key: str, member: Dict, justification: str) -> Dict:
        if not isinstance(member, dict):
            raise ValueError("member must be a dict containing at least 'email'")
        email = member.get("email")
        if not email:
            raise ValueError("member.email is required")

        user_id = self._ensure_user_id_from_email(email)
        if not hasattr(identity_store, "create_group_membership"):
            raise IntegrationError(
                "aws identity_store missing create_group_membership", response=None
            )
        resp = identity_store.create_group_membership(group_key, user_id)
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
        return self._map_aws_member_to_normalized(member_payload)

    def _remove_member(self, group_key: str, member: Dict, justification: str) -> Dict:
        if not isinstance(member, dict):
            raise ValueError("member must be a dict containing at least 'email'")
        email = member.get("email")
        if not email:
            raise ValueError("member.email is required")
        user_id = self._ensure_user_id_from_email(email)
        membership_id = self._resolve_membership_id(group_key, user_id)
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
        return self._map_aws_member_to_normalized(member_payload)

    def _get_group_members(self, group_key: str) -> List[Dict]:
        if not hasattr(identity_store, "list_group_memberships"):
            raise IntegrationError(
                "aws identity_store missing list_group_memberships", response=None
            )
        resp = identity_store.list_group_memberships(group_key)
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
                members.append(self._map_aws_member_to_normalized(member_payload))
                continue
            member_payload["id"] = member_id
            member_payload["email"] = None
            members.append(self._map_aws_member_to_normalized(member_payload))
        return members

    def _validate_permissions(self, user_key: str, group_key: str, action: str) -> bool:
        user_groups = self._get_user_managed_groups(user_key)
        return any(group.get("id") == group_key for group in user_groups)

    # Module-level sync helpers (kept below) are the canonical sync
    # implementations. Providers implement the sync_* methods below and
    # delegate to those helpers. We intentionally avoid duplicating
    # non-suffixed instance methods to reduce confusion.

    # ------------------------------------------------------------------
    # Sync implementations required by the sync-first GroupProvider base
    # class. These delegate to the existing module-level sync helpers so
    # providers remain sync-capable.
    # ------------------------------------------------------------------
    def get_user_managed_groups_sync(self, user_key: str) -> List[Dict]:
        return self._get_user_managed_groups(user_key)

    def add_member_sync(self, group_key: str, member: Dict, justification: str) -> Dict:
        return self._add_member(group_key, member, justification)

    def remove_member_sync(
        self, group_key: str, member: Dict, justification: str
    ) -> Dict:
        return self._remove_member(group_key, member, justification)

    def get_group_members_sync(self, group_key: str, **kwargs) -> List[Dict]:
        return self._get_group_members(group_key)

    def validate_permissions_sync(
        self, user_key: str, group_key: str, action: str
    ) -> bool:
        return self._validate_permissions(user_key, group_key, action)


# Register an instance of the provider
register_provider("aws")(AwsIdentityCenterProvider())
