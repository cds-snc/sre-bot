"""Canonical typed models for directory provider results."""

from dataclasses import dataclass
from typing import Optional

__all__ = [
    "DirectoryUser",
    "DirectoryMember",
    "DirectoryGroup",
    "MembershipCheckResult",
]


@dataclass(frozen=True)
class DirectoryUser:
    """Canonical user returned by all directory providers."""

    email: str
    provider_user_id: str
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
    provider: Optional[str] = None


@dataclass(frozen=True)
class DirectoryMember:
    """Canonical member returned by all directory providers."""

    email: str
    membership_id: Optional[str] = None
    provider_user_id: Optional[str] = None
    role: Optional[str] = None
    provider: Optional[str] = None


@dataclass(frozen=True)
class DirectoryGroup:
    """Canonical managed group returned by all directory providers."""

    group_email: str
    group_slug: str
    provider_group_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    provider: Optional[str] = None


@dataclass(frozen=True)
class MembershipCheckResult:
    """Canonical membership-check result."""

    group_email: str
    group_slug: str
    provider_group_id: Optional[str]
    user_email: str
    is_member: bool
