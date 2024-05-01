"""Module to sync the AWS Identity Center with the Google Workspace."""
import json
from logging import getLogger
from integrations.aws import identity_store
from modules.provisioning import users, groups
from utils import filters


logger = getLogger(__name__)


def synchronize(**kwargs):
    """Sync the AWS Identity Center with the Google Workspace."""
    sync_users = kwargs.get("sync_users", True)
    sync_groups = kwargs.get("sync_groups", True)
    query = kwargs.get("query", "email:aws-*")

    users_sync_status = None
    groups_sync_status = None

    source_groups_filters = [lambda group: "AWS-" in group["name"]]
    source_groups = groups.get_groups_with_members_from_integration(
        "google_groups", query=query, filters=source_groups_filters
    )
    source_users = users.get_unique_users_from_groups(source_groups, "members")

    logger.info(
        f"Found {len(source_groups)} Source Groups and {len(source_users)} Users"
    )

    target_groups = groups.get_groups_with_members_from_integration(
        "aws_identity_center"
    )
    target_users = identity_store.list_users()

    logger.info(
        f"Found {len(target_groups)} Target Groups and {len(target_users)} Users"
    )

    if sync_users:
        users_sync_status = sync_identity_center_users(source_users, **kwargs)

    if sync_groups:
        groups_sync_status = sync_identity_center_groups(
            source_groups, target_groups, target_users, **kwargs
        )

    else:
        groups_sync_status = None

    # return users_sync_status, groups_sync_status
    return users_sync_status, groups_sync_status


def create_aws_users(users_to_create):
    """Create the users in the identity store.

    Args:
        users_to_create (list): A list of users to create.

    Returns:
        list: A list of ID of the users created.
    """
    users_created = []
    for user in users_to_create:
        logger.info(
            f"Creating user {user['name']['givenName']} {user['name']['familyName']}, primary email: {user['primaryEmail']}"
        )
        response = identity_store.create_user(
            user["primaryEmail"], user["name"]["givenName"], user["name"]["familyName"]
        )
        if response:
            users_created.append(response)

    return users_created


def delete_aws_users(users_to_delete):
    """Delete the users in the identity store.

    Args:
        users_to_delete (list): A list of users to delete.

    Returns:
        list: A list of users deleted."""
    users_deleted = []
    for user in users_to_delete:
        logger.info(f"Deleting user {user['UserName']} with id: {user['UserId']}")
        response = identity_store.delete_user(user["UserId"])
        if response:
            users_deleted.append(user)
    return users_deleted


def sync_identity_center_users(source_users, target_users, **kwargs):
    enable_delete = kwargs.get("enable_delete", False)
    delete_target_all = kwargs.get("delete_target_all", False)

    users_to_create, users_to_delete = filters.compare_lists(
        {"values": source_users, "key": "primaryEmail"},
        {"values": target_users, "key": "UserName"},
        mode="sync",
        enable_delete=enable_delete,
        delete_target_all=delete_target_all,
    )
    logger.info(
        f"Identified {len(users_to_create)} Users to Create and {len(users_to_delete)} Users to Delete"
    )

    created_users = create_aws_users(users_to_create)
    deleted_users = delete_aws_users(users_to_delete)

    users_sync_status = created_users, deleted_users
    return users_sync_status


def create_group_memberships(group, users_to_add, target_users):
    memberships_created = []
    if not target_users:
        return memberships_created
    for user in users_to_add:
        matching_target_user = filters.filter_by_condition(
            target_users, lambda target_user: target_user["UserName"] == user["primaryEmail"]
        )
        if not matching_target_user:
            continue
        membership_id = identity_store.create_group_membership(
            group["GroupId"], matching_target_user["UserId"]
        )
        if membership_id:
            memberships_created.append(membership_id)
            logger.info(
                f"Added user {user['name']['fullName']} to group {group['DisplayName']}"
            )
    return memberships_created


def delete_group_memberships(group, users_to_remove):
    memberships_deleted = []
    logger.info(f"DEBUG: Group {json.dumps(group, indent=2)}")
    for user in users_to_remove:
        # membership = filters.filter_by_condition(
        #     group["GroupMemberships"],
        #     lambda membership: membership["MemberId"]["UserName"]
        #     == user["primaryEmail"],
        # )
        # if membership:
        # logger.info(
        #     f"Deleting user {user['name']['givenName']} from group {group['DisplayName']}"
        # )
        logger.info(f"Deleting user:\n{json.dumps(user, indent=2)}")

        # response = identity_store.delete_group_membership(
        #     membership["MembershipId"]
        # )
        # if response:
        #     memberships_deleted.append(membership)
    return memberships_deleted


def sync_identity_center_groups(source_groups, target_groups, target_users, **kwargs):
    for group in source_groups:
        group["DisplayName"] = group["name"].replace("AWS-", "")
    source_groups_to_sync, target_groups_to_sync = filters.compare_lists(
        {"values": source_groups, "key": "DisplayName"},
        {"values": target_groups, "key": "DisplayName"},
        mode="match",
    )
    logger.info(
        f"Found {len(source_groups_to_sync)} Source Groups and {len(target_groups_to_sync)} Target Groups to Sync"
    )
    for i in range(len(source_groups_to_sync)):
        logger.info(f"DEBUG: {json.dumps(source_groups_to_sync[i], indent=2)}")
        if (
            source_groups_to_sync[i]["DisplayName"]
            == target_groups_to_sync[i]["DisplayName"]
        ):
            users_to_add, users_to_remove = filters.compare_lists(
                {"values": source_groups_to_sync[i]["members"], "key": "email"},
                {
                    "values": target_groups_to_sync[i]["GroupMemberships"],
                    "key": "MemberId.UserName",
                },
                mode="sync",
                enable_delete=True,
            )
            logger.info(
                f"Adding {len(users_to_add)} users to group {target_groups_to_sync[i]['DisplayName']}"
            )
            groups_memberships_created = create_group_memberships(
                target_groups_to_sync[i], users_to_add
            )
            groups_memberships_deleted = delete_group_memberships(
                target_groups_to_sync[i], users_to_remove
            )

            return groups_memberships_created, groups_memberships_deleted
