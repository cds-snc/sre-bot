from typing import List, Optional
from pydantic import BaseModel


class ExternalId(BaseModel):
    Issuer: Optional[str]
    Id: Optional[str]


class Group(BaseModel):
    GroupId: Optional[str]
    DisplayName: Optional[str]
    ExternalIds: Optional[List[ExternalId]] = []
    Description: Optional[str]
    IdentityStoreId: Optional[str]


class GroupsListResponse(BaseModel):
    Groups: List[Group] = []
    NextToken: Optional[str]


class Name(BaseModel):
    Formatted: Optional[str]
    FamilyName: Optional[str]
    GivenName: Optional[str]
    MiddleName: Optional[str]
    HonorificPrefix: Optional[str]
    HonorificSuffix: Optional[str]


class Email(BaseModel):
    Value: Optional[str]
    Type: Optional[str]
    Primary: Optional[bool]


class Address(BaseModel):
    StreetAddress: Optional[str]
    Locality: Optional[str]
    Region: Optional[str]
    PostalCode: Optional[str]
    Country: Optional[str]
    Formatted: Optional[str]
    Type: Optional[str]
    Primary: Optional[bool]


class PhoneNumber(BaseModel):
    Value: Optional[str]
    Type: Optional[str]
    Primary: Optional[bool]


class User(BaseModel):
    UserName: Optional[str]
    UserId: Optional[str]
    ExternalIds: Optional[List[ExternalId]] = []
    Name: Optional[Name]
    DisplayName: Optional[str]
    NickName: Optional[str]
    ProfileUrl: Optional[str]
    Emails: Optional[List[Email]] = []
    Addresses: Optional[List[Address]] = []
    PhoneNumbers: Optional[List[PhoneNumber]] = []
    UserType: Optional[str]
    Title: Optional[str]
    PreferredLanguage: Optional[str]
    Locale: Optional[str]
    Timezone: Optional[str]
    IdentityStoreId: Optional[str]


class UsersListResponse(BaseModel):
    Users: List[User] = []
    NextToken: Optional[str]


class MemberId(BaseModel):
    UserId: Optional[str]


class GroupMembership(BaseModel):
    IdentityStoreId: Optional[str]
    MembershipId: Optional[str]
    GroupId: Optional[str]
    MemberId: Optional[MemberId]


class GroupMembershipsListResponse(BaseModel):
    GroupMemberships: List[GroupMembership] = []
    NextToken: Optional[str]
