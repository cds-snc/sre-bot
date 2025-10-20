from typing import List, Optional
from pydantic import BaseModel


class Group(BaseModel):
    id: Optional[str]
    email: Optional[str]
    name: Optional[str]
    description: Optional[str]
    directMembersCount: Optional[int]


class GroupsListResponse(BaseModel):
    kind: Optional[str]
    etag: Optional[str]
    groups: List[Group] = []
    nextPageToken: Optional[str]


class Member(BaseModel):
    kind: Optional[str]
    email: Optional[str]
    role: Optional[str]
    type: Optional[str]
    status: Optional[str]
    id: Optional[str]


class MembersListResponse(BaseModel):
    kind: Optional[str]
    etag: Optional[str]
    members: List[Member] = []
    nextPageToken: Optional[str]


class User(BaseModel):
    id: Optional[str]
    primaryEmail: Optional[str]
    name: Optional[dict]
    suspended: Optional[bool]
    emails: Optional[list]


class UsersListResponse(BaseModel):
    kind: Optional[str]
    etag: Optional[str]
    users: List[User] = []
    nextPageToken: Optional[str]
