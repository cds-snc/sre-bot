import pytest

# Google API Python Client


# Google Discovery Directory Resource
# Base fixtures
@pytest.fixture
def google_groups():
    def _google_groups(n=3, prefix="", domain="test.com"):
        return [
            {
                "id": f"{prefix}google_group_id{i+1}",
                "name": f"{prefix}group-name{i+1}",
                "email": f"{prefix}group-name{i+1}@{domain}",
                "description": f"{prefix}description{i+1}",
                "directMembersCount": i + 1,
            }
            for i in range(n)
        ]

    return _google_groups


@pytest.fixture
def google_users():
    def _google_users(n=3, prefix="", domain="test.com"):
        users = []
        for i in range(n):
            user = {
                "id": f"{prefix}user_id{i+1}",
                "primaryEmail": f"{prefix}user-email{i+1}@{domain}",
                "emails": [
                    {
                        "address": f"{prefix}user-email{i+1}@{domain}",
                        "primary": True,
                        "type": "work",
                    }
                ],
                "suspended": False,
                "name": {
                    "fullName": f"Given_name_{i+1} Family_name_{i+1}",
                    "familyName": f"Family_name_{i+1}",
                    "givenName": f"Given_name_{i+1}",
                    "displayName": f"Given_name_{i+1} Family_name_{i+1}",
                },
            }
            users.append(user)
        return users

    return _google_users


@pytest.fixture
def google_group_members(google_users):
    def _google_group_members(n=3, prefix="", domain="test.com"):
        users = google_users(n, prefix, domain)
        return [
            {
                "kind": "admin#directory#member",
                "email": user["primaryEmail"],
                "role": "MEMBER",
                "type": "USER",
                "status": "ACTIVE",
                "id": user["id"],
            }
            for user in users
        ]

    return _google_group_members


# Fixture with users
@pytest.fixture
def google_groups_w_users(google_groups, google_group_members, google_users):
    def _google_groups_w_users(
        n_groups=1, n_users=3, group_prefix="", user_prefix="", domain="test.com"
    ):
        groups = google_groups(n_groups, prefix=group_prefix, domain=domain)
        members = google_group_members(n_users, prefix=user_prefix, domain=domain)
        users = google_users(n_users, prefix=user_prefix, domain=domain)

        combined_members = []
        for member, user in zip(members, users):
            combined_member = {**member, **user}
            combined_members.append(combined_member)

        for group in groups:
            group["members"] = combined_members
        return groups

    return _google_groups_w_users


# AWS API fixtures


@pytest.fixture
def aws_users():
    def _aws_users(n=3, prefix="", domain="test.com", store_id="d-123412341234"):
        users = []
        for i in range(n):
            user = {
                "UserName": f"{prefix}user-email{i+1}@{domain}",
                "UserId": f"{prefix}user_id{i+1}",
                "Name": {
                    "FamilyName": f"Family_name_{i+1}",
                    "GivenName": f"Given_name_{i+1}",
                },
                "DisplayName": f"Given_name_{i+1} Family_name_{i+1}",
                "Emails": [
                    {
                        "Value": f"{prefix}user-email{i+1}@{domain}",
                        "Type": "work",
                        "Primary": True,
                    }
                ],
                "IdentityStoreId": f"{store_id}",
            }
            users.append(user)
        return users

    return _aws_users


@pytest.fixture
def aws_groups():
    def _aws_groups(n=3, prefix="", store_id="d-123412341234"):
        return [
            {
                "GroupId": f"{prefix}aws-group_id{i+1}",
                "DisplayName": f"{prefix}group-name{i+1}",
                "Description": f"A group to test resolving AWS-group{i+1} memberships",
                "IdentityStoreId": f"{store_id}",
            }
            for i in range(n)
        ]

    return _aws_groups


@pytest.fixture
def aws_groups_memberships():
    def _aws_groups_memberships(n=3, prefix="", group_id=1, store_id="d-123412341234"):
        return {
            "GroupMemberships": [
                {
                    "IdentityStoreId": f"{store_id}",
                    "MembershipId": f"{prefix}membership_id_{i+1}",
                    "GroupId": f"{prefix}aws-group_id{group_id}",
                    "MemberId": {
                        "UserId": f"{prefix}user_id{i+1}",
                    },
                }
                for i in range(n)
            ]
        }

    return _aws_groups_memberships


@pytest.fixture
def aws_groups_w_users(aws_groups, aws_users, aws_groups_memberships):
    def _aws_groups_w_users(
        n_groups=1,
        n_users=3,
        group_prefix="",
        user_prefix="",
        domain="test.com",
        store_id="d-123412341234",
    ):
        groups = aws_groups(n_groups, group_prefix, store_id)
        users = aws_users(n_users, user_prefix, domain, store_id)
        for i, group in enumerate(groups):
            memberships = aws_groups_memberships(
                n_users, group_prefix, i + 1, store_id
            )["GroupMemberships"]
            group["GroupMemberships"] = [
                {**membership, "MemberId": user}
                for user, membership in zip(users, memberships)
            ]
        return groups

    return _aws_groups_w_users
