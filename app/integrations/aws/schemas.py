from pydantic import BaseModel


class ExternalId(BaseModel):
    Issuer: str | None = None
    Id: str | None = None


class Group(BaseModel):
    GroupId: str | None = None
    DisplayName: str | None = None
    Description: str | None = None
    IdentityStoreId: str | None = None
    ExternalIds: list[ExternalId] | None = None


class GroupsListResponse(BaseModel):
    Groups: list[Group] = []
    NextToken: str | None = None


class NameObject(BaseModel):
    Formatted: str | None = None
    FamilyName: str | None = None
    GivenName: str | None = None
    MiddleName: str | None = None
    HonorificPrefix: str | None = None
    HonorificSuffix: str | None = None


class Email(BaseModel):
    Value: str | None = None
    Type: str | None = None
    Primary: bool | None = None


class Address(BaseModel):
    StreetAddress: str | None = None
    Locality: str | None = None
    Region: str | None = None
    PostalCode: str | None = None
    Country: str | None = None
    Formatted: str | None = None
    Type: str | None = None
    Primary: bool | None = None


class PhoneNumber(BaseModel):
    Value: str | None = None
    Type: str | None = None
    Primary: bool | None = None


class User(BaseModel):
    UserName: str | None = None
    UserId: str | None = None
    ExternalIds: list[ExternalId] | None = []
    Name: NameObject | None = None
    DisplayName: str | None = None
    NickName: str | None = None
    ProfileUrl: str | None = None
    Emails: list[Email] | None = []
    Addresses: list[Address] | None = []
    PhoneNumbers: list[PhoneNumber] | None = []
    UserType: str | None = None
    Title: str | None = None
    PreferredLanguage: str | None = None
    Locale: str | None = None
    Timezone: str | None = None
    IdentityStoreId: str | None = None


class UsersListResponse(BaseModel):
    Users: list[User] = []
    NextToken: str | None = None


class MemberIdObject(BaseModel):
    UserId: str | None = None


class GroupMembership(BaseModel):
    IdentityStoreId: str | None = None
    MembershipId: str | None = None
    GroupId: str | None = None
    MemberId: MemberIdObject | None = None
    UserDetails: User | None = None


class GroupMembershipsListResponse(BaseModel):
    GroupMemberships: list[GroupMembership] = []
    NextToken: str | None = None
