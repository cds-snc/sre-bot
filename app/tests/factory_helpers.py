from integrations.google_workspace.schemas import Group, User, Member


def make_google_groups(n=3, prefix="", domain="test.com", as_model=False):
    groups = []
    for i in range(n):
        g = Group(
            kind="admin#directory#group",
            id=f"{prefix}google_group_id{i+1}",
            etag=f'"group-etag-{i+1}"',
            name=f"{prefix}group-name{i+1}",
            email=f"{prefix}group-name{i+1}@{domain}",
            description=f"{prefix}description{i+1}",
            directMembersCount=str(i + 1) if i % 2 == 0 else i + 1,
            adminCreated=False,
            nonEditableAliases=[f"{prefix}noneditable-group{i+1}@{domain}"],
            members=[],
        )
        groups.append(g)
    if as_model:
        return groups
    return [g.model_dump() for g in groups]


def make_google_users(n=3, prefix="", domain="test.com", as_model=False):
    users = []
    for i in range(n):
        u = User(
            id=f"{prefix}user_id{i+1}",
            primaryEmail=f"{prefix}user-email{i+1}@{domain}",
            emails=[
                {
                    "address": f"{prefix}user-email{i+1}@{domain}",
                    "primary": True,
                    "type": "work",
                }
            ],
            suspended=False,
            name={
                "fullName": f"Given_name_{i+1} Family_name_{i+1}",
                "familyName": f"Family_name_{i+1}",
                "givenName": f"Given_name_{i+1}",
                "displayName": f"Given_name_{i+1} Family_name_{i+1}",
            },
            aliases=[f"{prefix}alias{i+1}@{domain}"],
            nonEditableAliases=[f"{prefix}noneditable{i+1}@{domain}"],
            customerId=f"C0{i+1}cust",
            orgUnitPath="/Products",
            thumbnailPhotoUrl="https://example.com/avatar.jpg",
            thumbnailPhotoEtag='"etag"',
            recoveryEmail=f"{prefix}recovery{i+1}@example.com",
            recoveryPhone=f"+1555000{i+1}",
            isAdmin=False,
            isDelegatedAdmin=False,
            lastLoginTime="2025-10-21T17:46:26.000Z",
            creationTime="2021-04-08T13:44:27.000Z",
            agreedToTerms=True,
            archived=False,
            changePasswordAtNextLogin=False,
            ipWhitelisted=False,
            isMailboxSetup=True,
            isEnrolledIn2Sv=True,
            isEnforcedIn2Sv=True,
            includeInGlobalAddressList=True,
            languages=[{"languageCode": "en", "preference": "preferred"}],
        )
        users.append(u)
    if as_model:
        return users
    return [u.model_dump() for u in users]


def make_google_members(n=3, prefix="", domain="test.com", as_model=False):
    users = make_google_users(n, prefix=prefix, domain=domain, as_model=True)
    members = []
    for i, user in enumerate(users):
        m = Member(
            kind="admin#directory#member",
            etag=f'"member-etag-{i+1}"',
            id=user.id,
            email=user.primaryEmail,
            role="MEMBER",
            type="USER",
            status="ACTIVE",
            user=user,
            primaryEmail=user.primaryEmail,
            name=user.name.model_dump() if user.name else None,
            isAdmin=False,
            isDelegatedAdmin=False,
        )
        members.append(m)
    if as_model:
        return members
    return [m.model_dump() for m in members]
