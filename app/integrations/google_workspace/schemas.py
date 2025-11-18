from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator


class Name(BaseModel):
    givenName: Optional[str] = None
    familyName: Optional[str] = None
    fullName: Optional[str] = None
    displayName: Optional[str] = None

    model_config = {"extra": "ignore"}


class User(BaseModel):
    id: Optional[str] = None
    primaryEmail: Optional[str] = None
    name: Optional[Name] = None
    suspended: Optional[bool] = None
    emails: Optional[List[Dict[str, Any]]] = None
    aliases: Optional[List[str]] = None
    nonEditableAliases: Optional[List[str]] = None
    customerId: Optional[str] = None
    orgUnitPath: Optional[str] = None
    thumbnailPhotoUrl: Optional[str] = None
    thumbnailPhotoEtag: Optional[str] = None
    recoveryEmail: Optional[str] = None
    recoveryPhone: Optional[str] = None
    isAdmin: Optional[bool] = None
    isDelegatedAdmin: Optional[bool] = None
    lastLoginTime: Optional[str] = None
    creationTime: Optional[str] = None
    agreedToTerms: Optional[bool] = None
    archived: Optional[bool] = None
    changePasswordAtNextLogin: Optional[bool] = None
    ipWhitelisted: Optional[bool] = None
    isMailboxSetup: Optional[bool] = None
    isEnrolledIn2Sv: Optional[bool] = None
    isEnforcedIn2Sv: Optional[bool] = None
    includeInGlobalAddressList: Optional[bool] = None
    # languages can be a list of dicts in sample JSON; accept any for flexibility
    languages: Optional[List[Any]] = None

    model_config = {"extra": "ignore"}


class Member(BaseModel):
    kind: Optional[str] = None
    etag: Optional[str] = None
    id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    primaryEmail: Optional[str] = None
    name: Optional[Dict[str, Any]] = None
    isAdmin: Optional[bool] = None
    isDelegatedAdmin: Optional[bool] = None

    model_config = {"extra": "ignore"}


class Group(BaseModel):
    kind: Optional[str] = None
    id: Optional[str] = None
    etag: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    # directMembersCount may be returned as string by API; accept both and coerce to int when possible
    directMembersCount: Optional[Union[int, str]] = None
    adminCreated: Optional[bool] = None
    nonEditableAliases: Optional[List[str]] = None

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
    user: Optional[User] = None

    model_config = {"extra": "ignore"}


# Assembled group model that includes members (enriched)
class GroupWithMembers(Group):
    members: List[MemberWithUser] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class GroupsResult(BaseModel):
    result: List[Group] = Field(default_factory=list)
    time: Optional[float] = None
    summary: Optional[str] = None

    model_config = {"extra": "ignore"}


# Backwards-compatible list response types (keep for existing tests/code)
class GroupsListResponse(BaseModel):
    kind: Optional[str]
    etag: Optional[str]
    groups: List[Group] = Field(default_factory=list)
    nextPageToken: Optional[str]

    model_config = {"extra": "ignore"}


class MembersListResponse(BaseModel):
    kind: Optional[str]
    etag: Optional[str]
    members: List[Member] = Field(default_factory=list)
    nextPageToken: Optional[str]

    model_config = {"extra": "ignore"}


class UsersListResponse(BaseModel):
    kind: Optional[str]
    etag: Optional[str]
    users: List[User] = Field(default_factory=list)
    nextPageToken: Optional[str]

    model_config = {"extra": "ignore"}
