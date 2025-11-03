from typing import Dict, List, Optional, Any

from integrations.aws import identity_store_next as identity_store
from integrations.aws.schemas import (
    User as AwsUser,
    Group as AwsGroup,
    GroupMembership as AwsGroupMembership,
)
from modules.groups.errors import IntegrationError
from modules.groups.providers import register_provider
from modules.groups.models import (
    as_canonical_dict,
    NormalizedMember,
    NormalizedGroup,
)
from modules.groups.providers.base import (
    GroupProvider,
    ProviderCapabilities,
    opresult_wrapper,
)


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
        normalized group contract with normalized members.

        Args:
            group: A dict response from AWS Identity Store API.
            members: Optional pre-fetched member list to include in the group.

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

        normalized_members = []
        if isinstance(raw_memberships, list):
            for m in raw_memberships:
                if isinstance(m, dict):
                    normalized_members.append(self._normalize_member_from_aws(m))

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
    def _add_member_impl(self, group_key: str, member_data: dict | str) -> dict:
        """Add a member to a group and return the normalized member dict.

        Args:
            group_key: AWS group key.
            member_data: Member identifier (str email) or dict with email.

        Returns:
            A canonical member dict (normalized NormalizedMember).
        """
        if not isinstance(member_data, dict):
            raise ValueError("member_data must be a dict containing at least 'email'")
        email = member_data.get("email")
        if not email:
            raise ValueError("member_data.email is required")

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
        return as_canonical_dict(self._normalize_member_from_aws(member_payload))

    @opresult_wrapper(data_key="result")
    def _remove_member_impl(self, group_key: str, member_data: dict | str) -> dict:
        """Remove a member from a group and return the normalized member dict.

        Args:
            group_key: AWS group key.
            member_data: Member identifier (str email) or dict with email.

        Returns:
            A canonical member dict (normalized NormalizedMember).
        """
        if not isinstance(member_data, dict):
            raise ValueError("member_data must be a dict containing at least 'email'")
        email = member_data.get("email")
        if not email:
            raise ValueError("member_data.email is required")
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
        return as_canonical_dict(self._normalize_member_from_aws(member_payload))

    @opresult_wrapper(data_key="members")
    def _get_group_members_impl(self, group_key: str, **kwargs) -> list[dict]:
        """AWS returns the list of canonical memberships, not the user details."""
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
