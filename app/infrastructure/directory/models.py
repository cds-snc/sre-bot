"""Canonical typed models for directory provider results."""

from dataclasses import dataclass

from infrastructure.operations.status import OperationStatus

__all__ = [
    "DirectoryUser",
    "DirectoryMember",
    "DirectoryGroup",
    "DirectoryGroupWithMembers",
    "DirectoryGroupFailure",
    "DirectoryGroupsWithMembers",
    "MembershipCheckResult",
]


@dataclass(frozen=True)
class DirectoryUser:
    """Canonical user returned by all directory providers."""

    email: str
    provider_user_id: str
    display_name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
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
    """Canonical group returned by all directory providers.

    ``aliases`` holds the secondary addresses the identity provider reports as
    routing to this group. It is a vendor-neutral fact, not a policy decision:
    consumers decide which address is canonical, never this model. It never
    repeats ``group_email``, and it is empty when the provider has no such
    concept, so no consumer may treat a non-empty tuple as guaranteed.

    Per-provider source: Google merges ``aliases[]`` and ``nonEditableAliases[]``;
    Entra ID maps ``proxyAddresses`` with the primary ``SMTP:`` entry dropped and
    the scheme prefix stripped.
    """

    group_email: str
    group_slug: str
    provider_group_id: str
    name: str | None = None
    description: str | None = None
    provider: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class DirectoryGroupWithMembers:
    """Canonical group paired with its resolved members."""

    group: DirectoryGroup
    members: tuple[DirectoryMember, ...] = ()


@dataclass(frozen=True)
class DirectoryGroupFailure:
    """Per-group failure carried inside a successful composition result."""

    group_email: str
    status: OperationStatus
    error_code: str | None
    message: str


@dataclass(frozen=True)
class DirectoryGroupsWithMembers:
    """Groups-with-members composition payload.

    Per-group failures live here rather than in the result status because the
    OperationStatus set is closed (decisions/operation-result.md).
    """

    groups: tuple[DirectoryGroupWithMembers, ...] = ()
    failures: tuple[DirectoryGroupFailure, ...] = ()


@dataclass(frozen=True)
class MembershipCheckResult:
    """Canonical membership-check result."""

    group_email: str
    group_slug: str
    provider_group_id: str | None
    user_email: str
    is_member: bool
