import os


def make_aws_users(n=3, prefix="", domain="test.com", store_id="d-123412341234"):
    users = []
    for i in range(n):
        user = {
            "UserName": f"{prefix}user-email{i + 1}@{domain}",
            "UserId": f"{prefix}user_id{i + 1}",
            "Name": {
                "FamilyName": f"Family_name_{i + 1}",
                "GivenName": f"Given_name_{i + 1}",
            },
            "DisplayName": f"Given_name_{i + 1} Family_name_{i + 1}",
            "Emails": [
                {
                    "Value": f"{prefix}user-email{i + 1}@{domain}",
                    "Type": "work",
                    "Primary": True,
                }
            ],
            "IdentityStoreId": f"{store_id}",
        }
        users.append(user)
    return users


def make_aws_groups(n=3, prefix="", store_id="d-123412341234"):
    return [
        {
            "GroupId": f"{prefix}aws-group_id{i + 1}",
            "DisplayName": f"{prefix}group-name{i + 1}",
            "Description": f"A group to test resolving AWS-group{i + 1} memberships",
            "IdentityStoreId": f"{store_id}",
        }
        for i in range(n)
    ]


def make_aws_groups_memberships(n=3, prefix="", group_id=1, store_id="d-123412341234"):
    return {
        "GroupMemberships": [
            {
                "IdentityStoreId": f"{store_id}",
                "MembershipId": f"{prefix}membership_id_{i + 1}",
                "GroupId": f"{prefix}aws-group_id{group_id}",
                "MemberId": {
                    "UserId": f"{prefix}user_id{i + 1}",
                },
            }
            for i in range(n)
        ]
    }


def make_aws_groups_w_users_with_legacy(
    n_groups=1,
    n_users=3,
    group_prefix="",
    user_prefix="",
    domain="test.com",
    store_id="d-123412341234",
):
    groups = make_aws_groups(n_groups, group_prefix, store_id)
    users = make_aws_users(n_users, user_prefix, domain, store_id)
    for i, group in enumerate(groups):
        memberships = make_aws_groups_memberships(n_users, group_prefix, i + 1, store_id)["GroupMemberships"]
        group["GroupMemberships"] = [{**membership, "MemberId": user} for user, membership in zip(users, memberships)]
    return groups


def make_aws_groups_w_users(
    n_groups=1,
    n_users=3,
    group_prefix="",
    user_prefix="",
    domain="test.com",
    store_id="d-123412341234",
):
    groups = make_aws_groups(n_groups, group_prefix, store_id)
    users = make_aws_users(n_users, user_prefix, domain, store_id)
    for i, group in enumerate(groups):
        memberships = make_aws_groups_memberships(n_users, group_prefix, i + 1, store_id)["GroupMemberships"]
        group["GroupMemberships"] = []
        for user, membership in zip(users, memberships):
            user_details = user.copy()
            user_details["Emails"] = [{**email, "Type": email["Type"].upper()} for email in user_details.get("Emails", [])]
            group["GroupMemberships"].append({**membership, "UserDetails": user_details})
    return groups


DEFAULT_INSTANCE_ID = "d-1234567890"
DEFAULT_INSTANCE_ARN = "arn:aws:sso:::instance/ssoins-1234567890abcdef"


def set_aws_tenant(
    monkeypatch,
    *,
    instance_id=None,
    instance_arn=None,
    audit_role_arn=None,
    org_role_arn=None,
    logging_role_arn=None,
):
    """Name an AWS tenant through the AWS__TENANT__<FIELD> variables.

    The Identity Center pair is required by the entry, so a test that names only a role
    gets a valid default pair; each argument given overrides its variable, and a role
    left out stays unset.
    """
    values = {
        "INSTANCE_ID": instance_id,
        "INSTANCE_ARN": instance_arn,
        "AUDIT_ROLE_ARN": audit_role_arn,
        "ORG_ROLE_ARN": org_role_arn,
        "LOGGING_ROLE_ARN": logging_role_arn,
    }
    defaults = {"INSTANCE_ID": DEFAULT_INSTANCE_ID, "INSTANCE_ARN": DEFAULT_INSTANCE_ARN}
    for field, value in values.items():
        name = f"AWS__TENANT__{field}"
        if value is not None:
            monkeypatch.setenv(name, value)
        elif field in defaults and not os.environ.get(name):
            monkeypatch.setenv(name, defaults[field])
