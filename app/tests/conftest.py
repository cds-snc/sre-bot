import pytest
from tests.factory_helpers import (
    make_google_groups,
    make_google_users,
    make_google_members,
)

# Google API Python Client


# Google Discovery Directory Resource
# Legacy Fixtures
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


# Additional fixtures for comprehensive testing
@pytest.fixture
def google_groups_with_legacy_structure(
    google_group_factory, google_member_factory, google_user_factory
):
    """Factory to create groups with legacy-compatible member structure."""

    def _factory(n_groups=1, n_members_per_group=2, domain="test.com"):
        groups = google_group_factory(n_groups, domain=domain)
        result = []

        for i, group in enumerate(groups):
            # Create members for this group
            members = google_member_factory(
                n_members_per_group, prefix=f"g{i}-", domain=domain
            )
            users = google_user_factory(
                n_members_per_group, prefix=f"g{i}-", domain=domain
            )

            # Create legacy-compatible members with flattened user details
            legacy_members = []
            for member, user in zip(members, users):
                # Ensure email consistency
                member["email"] = user["primaryEmail"]

                # Create legacy member with flattened user details
                legacy_member = {**member}
                legacy_member["user_details"] = user

                # Flatten user details into top-level member dict (legacy compatibility)
                for k, v in user.items():
                    if k not in legacy_member:
                        legacy_member[k] = v

                legacy_members.append(legacy_member)

            group_with_members = {**group}
            group_with_members["members"] = legacy_members
            result.append(group_with_members)

        return result

    return _factory


# --- Google Directory API Pydantic factories ---


@pytest.fixture
def google_group_factory():
    """
    Factory fixture to generate a list of valid Google Group dicts for tests.
    Usage:
        groups = google_group_factory(n=2, prefix="dev-")
        # returns a list of dicts (model_dump)
    """

    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        # Delegate to shared helper to avoid duplicated logic
        return make_google_groups(n=n, prefix=prefix, domain=domain, as_model=as_model)

    return _factory


@pytest.fixture
def google_user_factory():
    """
    Factory fixture to generate a list of valid Google User dicts or models for tests.
    Usage:
        users = google_user_factory(n=2, prefix="dev-")
        # returns a list of dicts (model_dump)
        users = google_user_factory(n=2, as_model=True)
        # returns a list of User models
    """

    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        # Delegate to shared helper to avoid duplicated logic
        return make_google_users(n=n, prefix=prefix, domain=domain, as_model=as_model)

    return _factory


@pytest.fixture
def google_member_factory():
    """
    Factory fixture to generate a list of valid Google Member dicts or models for tests.
    Usage:
        members = google_member_factory(n=2, prefix="dev-")
        # returns a list of dicts (model_dump)
        members = google_member_factory(n=2, as_model=True)
        # returns a list of Member models
    """

    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        # Delegate to shared helper to avoid duplicated logic
        return make_google_members(n=n, prefix=prefix, domain=domain, as_model=as_model)

    return _factory


@pytest.fixture
def google_batch_response_factory():
    """Factory to create Google API batch response structures."""

    def _factory(success_responses=None, error_responses=None):
        results = {}

        if success_responses:
            results.update(success_responses)

        if error_responses:
            # Add error responses - could be None or error objects
            results.update(error_responses)

        return {"results": results}

    return _factory


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
