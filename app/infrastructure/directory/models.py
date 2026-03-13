"""Canonical typed models for directory provider results."""

from dataclasses import dataclass
from typing import Optional

__all__ = [
    "DirectoryMember",
    "DirectoryGroup",
    "MembershipCheckResult",
]


@dataclass(frozen=True)
class DirectoryMember:
    """Canonical member returned by all directory providers."""

    email: str
    member_id: Optional[str] = None
    role: Optional[str] = None
    provider: Optional[str] = None


@dataclass(frozen=True)
class DirectoryGroup:
    """Canonical group returned by all directory providers."""

    group_key: str
    email: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    provider: Optional[str] = None


@dataclass(frozen=True)
class MembershipCheckResult:
    """Canonical membership-check result."""

    group_key: str
    email: str
    is_member: bool
