import os
from integrations.aws.client import paginate, assume_role_client

INSTANCE_ID = os.environ.get("AWS_SSO_INSTANCE_ID", "")
INSTANCE_ARN = os.environ.get("AWS_SSO_INSTANCE_ARN", "")
ROLE_ARN = os.environ.get("AWS_SSO_ROLE_ARN", "")


def list_users(identity_store_id=None, attribute_path=None, attribute_value=None):
    """Retrieves all users from the AWS Identity Center (identitystore)"""
    client = assume_role_client("identitystore", ROLE_ARN)
    if not identity_store_id:
        identity_store_id = INSTANCE_ID
    kwargs = {"IdentityStoreId": identity_store_id}

    if attribute_path and attribute_value:
        kwargs["Filters"] = [
            {"AttributePath": attribute_path, "AttributeValue": attribute_value},
        ]

    return paginate(client, "list_users", ["Users"], **kwargs)


def list_groups(identity_store_id=None, attribute_path=None, attribute_value=None):
    """Retrieves all groups from the AWS Identity Center (identitystore)"""
    client = assume_role_client("identitystore", ROLE_ARN)
    if not identity_store_id:
        identity_store_id = INSTANCE_ID
    kwargs = {"IdentityStoreId": identity_store_id}

    if attribute_path and attribute_value:
        kwargs["Filters"] = [
            {"AttributePath": attribute_path, "AttributeValue": attribute_value},
        ]

    return paginate(client, "list_groups", ["Groups"], **kwargs)


def list_group_memberships(identity_store_id, group_id):
    """Retrieves all group memberships from the AWS Identity Center  (identitystore)"""
    client = assume_role_client("identitystore", ROLE_ARN)

    if not identity_store_id:
        identity_store_id = INSTANCE_ID
    return paginate(
        client,
        "list_group_memberships",
        ["GroupMemberships"],
        IdentityStoreId=identity_store_id,
        GroupId=group_id,
    )


def list_groups_with_membership(identity_store_id):
    """Retrieves all groups with their members from the AWS Identity Center (identitystore)"""
    if not identity_store_id:
        identity_store_id = INSTANCE_ID
    groups = list_groups(identity_store_id)
    for group in groups:
        group["GroupMemberships"] = list_group_memberships(
            identity_store_id, group["GroupId"]
        )

    return groups
