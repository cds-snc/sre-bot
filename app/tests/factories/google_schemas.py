from typing import Any

from pydantic import BaseModel, Field, field_validator


class Name(BaseModel):
    givenName: str | None = None
    familyName: str | None = None
    fullName: str | None = None
    displayName: str | None = None

    model_config = {"extra": "ignore"}


class User(BaseModel):
    id: str | None = None
    primaryEmail: str | None = None
    name: Name | None = None
    suspended: bool | None = None
    emails: list[dict[str, Any]] | None = None
    aliases: list[str] | None = None
    nonEditableAliases: list[str] | None = None
    customerId: str | None = None
    orgUnitPath: str | None = None
    thumbnailPhotoUrl: str | None = None
    thumbnailPhotoEtag: str | None = None
    recoveryEmail: str | None = None
    recoveryPhone: str | None = None
    isAdmin: bool | None = None
    isDelegatedAdmin: bool | None = None
    lastLoginTime: str | None = None
    creationTime: str | None = None
    agreedToTerms: bool | None = None
    archived: bool | None = None
    changePasswordAtNextLogin: bool | None = None
    ipWhitelisted: bool | None = None
    isMailboxSetup: bool | None = None
    isEnrolledIn2Sv: bool | None = None
    isEnforcedIn2Sv: bool | None = None
    includeInGlobalAddressList: bool | None = None
    # languages can be a list of dicts in sample JSON; accept any for flexibility
    languages: list[Any] | None = None

    model_config = {"extra": "ignore"}


class Member(BaseModel):
    kind: str | None = None
    etag: str | None = None
    id: str | None = None
    email: str | None = None
    role: str | None = None
    type: str | None = None
    status: str | None = None
    primaryEmail: str | None = None
    name: dict[str, Any] | None = None
    isAdmin: bool | None = None
    isDelegatedAdmin: bool | None = None

    model_config = {"extra": "ignore"}


class Group(BaseModel):
    kind: str | None = None
    id: str | None = None
    etag: str | None = None
    email: str | None = None
    name: str | None = None
    description: str | None = None
    # directMembersCount may be returned as string by API; accept both and coerce to int when possible
    directMembersCount: int | str | None = None
    adminCreated: bool | None = None
    nonEditableAliases: list[str] | None = None

    model_config = {"extra": "ignore"}

    @field_validator("directMembersCount", mode="before")
    @classmethod
    def _coerce_direct_members_count(cls, v):
        if v is None:
            return None
        # Accept int already
        if isinstance(v, int):
            return v
        # Accept numeric strings
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        # Fallback: try to coerce to int
        try:
            return int(v)
        except Exception:
            return None


# Enriched member used for assembled responses (contains nested user details)
class MemberWithUser(Member):
    user: User | None = None

    model_config = {"extra": "ignore"}


# Assembled group model that includes members (enriched)
class GroupWithMembers(Group):
    members: list[MemberWithUser] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class GroupsResult(BaseModel):
    result: list[Group] = Field(default_factory=list)
    time: float | None = None
    summary: str | None = None

    model_config = {"extra": "ignore"}


# Backwards-compatible list response types (keep for existing tests/code)
class GroupsListResponse(BaseModel):
    kind: str | None
    etag: str | None
    groups: list[Group] = Field(default_factory=list)
    nextPageToken: str | None

    model_config = {"extra": "ignore"}


class MembersListResponse(BaseModel):
    kind: str | None
    etag: str | None
    members: list[Member] = Field(default_factory=list)
    nextPageToken: str | None

    model_config = {"extra": "ignore"}


class UsersListResponse(BaseModel):
    kind: str | None
    etag: str | None
    users: list[User] = Field(default_factory=list)
    nextPageToken: str | None

    model_config = {"extra": "ignore"}
