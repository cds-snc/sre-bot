"""Canonical typed models for directory provider results."""

from dataclasses import dataclass

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
    display_name: str | None = None
    is_active: bool | None = None
    provider: str | None = None


@dataclass(frozen=True)
class DirectoryMember:
    """Canonical member returned by all directory providers."""

    email: str
    membership_id: str | None = None
    provider_user_id: str | None = None
    member_type: str | None = None
    role: str | None = None
    provider: str | None = None


@dataclass(frozen=True)
class DirectoryGroup:
    """Canonical managed group returned by all directory providers."""

    group_email: str
    group_slug: str
    provider_group_id: str
    name: str | None = None
    description: str | None = None
    provider: str | None = None


@dataclass(frozen=True)
class MembershipCheckResult:
    """Canonical membership-check result."""

    group_email: str
    group_slug: str
    provider_group_id: str | None
    user_email: str
    is_member: bool
