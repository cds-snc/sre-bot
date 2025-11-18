from typing import List, Optional
from pydantic import BaseModel


class ExternalId(BaseModel):
    Issuer: Optional[str] = None
    Id: Optional[str] = None


class Group(BaseModel):
    GroupId: Optional[str] = None
    DisplayName: Optional[str] = None
    Description: Optional[str] = None
    IdentityStoreId: Optional[str] = None
    ExternalIds: Optional[List[ExternalId]] = None


class GroupsListResponse(BaseModel):
    Groups: List[Group] = []
    NextToken: Optional[str] = None


class NameObject(BaseModel):
    Formatted: Optional[str] = None
    FamilyName: Optional[str] = None
    GivenName: Optional[str] = None
    MiddleName: Optional[str] = None
    HonorificPrefix: Optional[str] = None
    HonorificSuffix: Optional[str] = None


class Email(BaseModel):
    Value: Optional[str] = None
    Type: Optional[str] = None
    Primary: Optional[bool] = None


class Address(BaseModel):
    StreetAddress: Optional[str] = None
    Locality: Optional[str] = None
    Region: Optional[str] = None
    PostalCode: Optional[str] = None
    Country: Optional[str] = None
    Formatted: Optional[str] = None
    Type: Optional[str] = None
    Primary: Optional[bool] = None


class PhoneNumber(BaseModel):
    Value: Optional[str] = None
    Type: Optional[str] = None
    Primary: Optional[bool] = None


class User(BaseModel):
    UserName: Optional[str] = None
    UserId: Optional[str] = None
    ExternalIds: Optional[List[ExternalId]] = []
    Name: Optional[NameObject] = None
    DisplayName: Optional[str] = None
    NickName: Optional[str] = None
    ProfileUrl: Optional[str] = None
    Emails: Optional[List[Email]] = []
    Addresses: Optional[List[Address]] = []
    PhoneNumbers: Optional[List[PhoneNumber]] = []
    UserType: Optional[str] = None
    Title: Optional[str] = None
    PreferredLanguage: Optional[str] = None
    Locale: Optional[str] = None
    Timezone: Optional[str] = None
    IdentityStoreId: Optional[str] = None


class UsersListResponse(BaseModel):
    Users: List[User] = []
    NextToken: Optional[str] = None


class MemberIdObject(BaseModel):
    UserId: Optional[str] = None


class GroupMembership(BaseModel):
    IdentityStoreId: Optional[str] = None
    MembershipId: Optional[str] = None
    GroupId: Optional[str] = None
    MemberId: Optional[MemberIdObject] = None
    UserDetails: Optional[User] = None


class GroupMembershipsListResponse(BaseModel):
    GroupMemberships: List[GroupMembership] = []
    NextToken: Optional[str] = None
