"""Provider-agnostic normalized data models for the groups module.

This module defines lightweight dataclass models used internally to represent
group and member data in a provider-neutral way. These are NOT Pydantic models
and do NOT provide runtime validation—they prioritize performance and simplicity.

Key purpose:
  - Canonical structures that all providers normalize to
  - Bridge between provider-specific APIs and business logic
  - Internal representation (not for external API responses)

Key distinctions:
  - models.py: Internal normalized structures (dataclasses, no validation)
  - schemas.py: API contracts with Pydantic (full validation)
  - types.py: Internal protocol hints (TypedDict, no validation)

Relationships:
  - NormalizedMember → Converted to MemberResponse for API responses (schemas.py)
  - NormalizedGroup → Converted to GroupResponse for API responses (schemas.py)
  - Helper functions (member_from_dict, group_from_dict) are used by providers
    to normalize provider-specific data into these structures

Usage:
  - Imported by: providers, orchestration.py, mappings.py, responses.py, reconciliation_worker.py
  - Providers should call member_from_dict() and group_from_dict() to normalize data
  - Business logic operates on NormalizedMember/NormalizedGroup before returning to API
"""

from dataclasses import dataclass, asdict
from typing import List, Optional, Any, Dict


@dataclass
class NormalizedMember:
    """Normalized representation of a group member.

    Lightweight dataclass (not Pydantic) for performance. Used internally
    to represent members in a provider-agnostic way.

    For API responses, convert to schemas.MemberResponse using Pydantic
    serialization.

    Attributes:
        email: The email address of the member.
        id: The unique identifier of the member.
        role: The role of the member in the group (e.g., 'owner', 'member').
        provider_member_id: The provider-specific identifier for the member.
        first_name: The first name of the member, if available.
        family_name: The family name of the member, if available.
        raw: The original raw data from the provider for reference.
    """

    email: Optional[str]
    id: Optional[str]
    role: Optional[str]
    provider_member_id: Optional[str]
    first_name: Optional[str] = None
    family_name: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


@dataclass
class NormalizedGroup:
    """Normalized representation of a group.

    Lightweight dataclass (not Pydantic) for performance. Used internally
    to represent groups in a provider-agnostic way.

    For API responses, convert to schemas.GroupResponse using Pydantic
    serialization.

    Attributes:
        id: The unique identifier of the group.
        name: The display name of the group.
        description: A brief description of the group.
        provider: The name of the provider (e.g., 'google', 'aws').
        members: A list of NormalizedMember instances representing group members.
        raw: The original raw data from the provider for reference.
    """

    id: Optional[str]
    name: Optional[str]
    description: Optional[str]
    provider: str
    members: List[NormalizedMember]
    raw: Optional[Dict[str, Any]] = None


def member_from_dict(d: dict, provider: str) -> NormalizedMember:
    """Convert a provider member dict into a NormalizedMember.

    Helper for providers to normalize their raw member data into the canonical
    internal structure. This function:
      1. Handles multiple provider-specific field name variations
      2. Preserves the original raw payload for debugging/provider-specific logic
      3. Returns a lightweight NormalizedMember for business logic use

    Args:
        d: Raw provider member data dict
        provider: Provider name (for context; not used in normalization)

    Returns:
        NormalizedMember with extracted/normalized fields and original raw data
    """

    # mark provider as used (keeps the signature stable for callers)
    _ = provider
    if not isinstance(d, dict):
        return NormalizedMember(
            email=None, id=None, role=None, provider_member_id=None, raw=None
        )
    email = d.get("email") or d.get("primaryEmail") or d.get("Email")
    member_id = d.get("id") or d.get("MemberId") or d.get("Id") or d.get("UserName")
    role = d.get("role") or d.get("Role")
    provider_member_id = d.get("memberKey") or member_id

    # Extract common name fields from different provider payload shapes
    first_name = (
        d.get("givenName")
        or d.get("GivenName")
        or (d.get("Name") or {}).get("GivenName")
        or (d.get("name") or {}).get("given")
        or None
    )
    family_name = (
        d.get("familyName")
        or d.get("FamilyName")
        or (d.get("Name") or {}).get("FamilyName")
        or (d.get("name") or {}).get("family")
        or None
    )

    # Fallback: try to split a displayName if present
    if not (first_name or family_name):
        display = d.get("displayName") or d.get("DisplayName")
        if isinstance(display, str) and " " in display:
            parts = display.split(None, 1)
            first_name = parts[0]
            family_name = parts[1]

    return NormalizedMember(
        email=email,
        id=member_id,
        role=role,
        provider_member_id=provider_member_id,
        first_name=first_name,
        family_name=family_name,
        raw=d,
    )


def group_from_dict(d: dict, provider: str) -> NormalizedGroup:
    """Convert a provider group dict into a NormalizedGroup.

    Helper for providers to normalize their raw group data into the canonical
    internal structure. This function:
      1. Handles multiple provider-specific field name variations
      2. Normalizes member data using member_from_dict()
      3. Preserves the original raw payload for debugging/provider-specific logic

    Args:
        d: Raw provider group data dict
        provider: Provider name used for context and member normalization

    Returns:
        NormalizedGroup with extracted/normalized fields, members, and original raw data
    """

    if not isinstance(d, dict):
        return NormalizedGroup(
            id=None,
            name=None,
            description=None,
            provider=provider,
            members=[],
            raw=None,
        )
    gid = d.get("id") or d.get("GroupId") or d.get("email") or d.get("GroupName")
    name = d.get("name") or d.get("DisplayName") or gid
    description = d.get("description") or d.get("Description")
    raw_members = (
        d.get("members") or d.get("GroupMemberships") or d.get("memberships") or []
    )
    members = [
        member_from_dict(m, provider) for m in raw_members if isinstance(m, dict)
    ]
    return NormalizedGroup(
        id=gid,
        name=name,
        description=description,
        provider=provider,
        members=members,
        raw=d,
    )


def as_canonical_dict(obj) -> dict:
    """Return a JSON-serializable canonical dict for a NormalizedGroup/Member.

    Converts dataclass instances to plain dicts suitable for JSON serialization.
    Providers can call this to return plain dictionaries to core flows or API
    layers without leaking provider internals.

    Args:
        obj: A NormalizedMember, NormalizedGroup, or already a dict.

    Returns:
        A plain dict representation suitable for JSON serialization.
    """

    try:
        return asdict(obj)
    except (TypeError, ValueError):
        return obj


# Type alias for a provider -> list of normalized groups mapping per provider
GroupsMap = Dict[str, List[NormalizedGroup]]
