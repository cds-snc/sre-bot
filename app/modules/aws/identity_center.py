"""Module to sync the AWS Identity Center with the Google Workspace."""
from logging import getLogger
from integrations.aws import identity_store
from modules.provisioning import users, groups
from utils import filters


logger = getLogger(__name__)
DRY_RUN = True


def synchronize(**kwargs):
    """Sync the AWS Identity Center with the Google Workspace.

    Args:
        enable_users_sync (bool): Toggle to sync users.
        enable_groups_sync (bool): Toggle to sync groups.
        query (str): The query to filter the Google Groups.

    Returns:
        tuple: A tuple containing the users sync status and groups sync status.
    """
    enable_users_sync = kwargs.pop("enable_users_sync", True)
    enable_groups_sync = kwargs.pop("enable_groups_sync", True)
    query = kwargs.pop("query", "email:aws-*")

    users_sync_status = None
    groups_sync_status = None

    source_groups_filters = [lambda group: "AWS-" in group["name"]]
    source_groups = groups.get_groups_with_members_from_integration(
        "google_groups", query=query, filters=source_groups_filters
    )
    source_users = filters.get_unique_nested_dicts(source_groups, "members")
    logger.info(
        f"synchronize:Found {len(source_groups)} Source Groups and {len(source_users)} Users"
    )

    for group in source_groups:
        logger.info(
            f"synchronize:Source:Group {group['name']} has {len(group['members'])} members"
        )
    for user in source_users:
        logger.info(f"synchronize:Source:User {user['primaryEmail']}")

    target_groups = groups.get_groups_with_members_from_integration(
        "aws_identity_center"
    )
    target_users = identity_store.list_users()

    logger.info(
        f"synchronize:Found {len(target_groups)} Target Groups and {len(target_users)} Users"
    )

    for group in target_groups:
        logger.info(
            f"synchronize:Target:Group {group['DisplayName']} has {len(group['GroupMemberships'])} members"
        )

    for user in target_users:
        logger.info(f"synchronize:Target:User {user['UserName']}")

    if enable_users_sync:
        logger.info("synchronize:users:Syncing Users")
        users_sync_status = sync_users(source_users, target_users, **kwargs)
        target_users = identity_store.list_users()

    if enable_groups_sync:
        logger.info("synchronize:groups:Syncing Groups")

        logger.info("synchronize:groups:Formatting Source Groups")
        source_groups = groups.preformat_groups(
            source_groups, "name", "DisplayName", pattern=r"^AWS-", replace=""
        )
        groups_sync_status = sync_groups(
            source_groups, target_groups, target_users, **kwargs
        )

    return {
        "users": users_sync_status,
        "groups": groups_sync_status,
    }


def create_aws_users(users_to_create):
    """Create the users in the identity store.

    Args:
        users_to_create (list): A list of users to create from the source system.

    Returns:
        list: A list of user ID of the users created.
    """
    logger.info(f"create_aws_users:Starting creation of {len(users_to_create)} users.")
    users_created = []
    for user in users_to_create:
        if not DRY_RUN:
            response = identity_store.create_user(
                user["primaryEmail"],
                user["name"]["givenName"],
                user["name"]["familyName"],
            )
            if response:
                logger.info(
                    f"create_aws_users:Successfully created user {user['primaryEmail']}"
                )
                users_created.append(response)
            else:
                logger.error(
                    f"create_aws_users:Failed to create user {user['primaryEmail']}"
                )
        else:
            logger.info(
                f"create_aws_users:DRY_RUN:Successfully created user {user['primaryEmail']}"
            )
            users_created.append(user["primaryEmail"])
    logger.info(f"create_aws_users:Finished creation of {len(users_created)} users.")
    return users_created


def delete_aws_users(users_to_delete, enable_user_delete=False):
    """Delete the users in the identity store.

    Args:
        users_to_delete (list): A list of users to delete from the target system.

    Returns:
        list: A list of user name of the users deleted.
    """
    logger.info(f"delete_aws_users:Starting deletion of {len(users_to_delete)} users.")
    users_deleted = []
    for user in users_to_delete:
        if enable_user_delete and not DRY_RUN:
            response = identity_store.delete_user(user["UserId"])
            if response:
                logger.info(
                    f"delete_aws_users:Successfully deleted user {user['UserName']}"
                )
                users_deleted.append(user["UserName"])
            else:
                logger.error(
                    f"delete_aws_users:Failed to delete user {user['UserName']}"
                )
        else:
            logger.info(
                f"delete_aws_users:DRY_RUN:Successfully deleted user {user['UserName']}"
            )
            users_deleted.append(user["UserName"])
    logger.info(f"delete_aws_users:Finished deletion of {len(users_deleted)} users.")
    return users_deleted


def sync_users(source_users, target_users, **kwargs):
    """Sync the users in the identity store.

    Args:

        source_users (list): A list of users from the source system.
        target_users (list): A list of users in the identity store.
        enable_user_delete (bool): Enable deletion of users.
        delete_target_all (bool): Mark all target users for deletion.

    Returns:
        tuple: A tuple containing the users created and deleted.
    """
    enable_user_delete = kwargs.get("enable_user_delete", False)
    delete_target_all = kwargs.get("delete_target_all", False)

    if delete_target_all:
        users_to_delete = target_users
        users_to_create = []
    else:
        users_to_create, users_to_delete = filters.compare_lists(
            {"values": source_users, "key": "primaryEmail"},
            {"values": target_users, "key": "UserName"},
            mode="sync",
        )
    logger.info(
        f"synchronize:users:Found {len(users_to_create)} Users to Create and {len(users_to_delete)} Users to Delete"
    )

    created_users = create_aws_users(users_to_create)
    deleted_users = delete_aws_users(
        users_to_delete, enable_user_delete=enable_user_delete
    )

    return created_users, deleted_users


def create_group_memberships(target_group, users_to_add, target_users):
    """Create group memberships for the users in the identity store.

    Args:
        group (dict): The group to add the users to.
        users_to_add (list): A list of users to add to the group.
        target_users (list): A list of users in the identity store.

    Returns:
        list: A list of group membership ID for memberships created.
    """
    memberships_created = []
    logger.info(
        f"create_group_memberships:Adding {len(users_to_add)} users to group {target_group['DisplayName']}"
    )
    for user in users_to_add:
        matching_target_users = filters.filter_by_condition(
            target_users,
            lambda target_user: target_user["UserName"] == user["primaryEmail"],
        )
        if matching_target_users:
            matching_target_user = matching_target_users[0]
        else:
            logger.info(
                f"create_group_memberships:Failed to find user {user['primaryEmail']} in target system"
            )
            continue
        if not DRY_RUN:
            response = identity_store.create_group_membership(
                target_group["GroupId"], matching_target_user["UserId"]
            )
            if response:
                logger.info(
                    f"create_group_memberships:Successfully added user {matching_target_user['UserName']} to group {target_group['DisplayName']}"
                )
                memberships_created.append(matching_target_user["UserName"])
            else:
                logger.error(
                    f"create_group_memberships:Failed to add user {matching_target_user['UserName']} to group {target_group['DisplayName']}"
                )
        else:
            logger.info(
                f"create_group_memberships:DRY_RUN:Successfully added user {matching_target_user['UserName']} to group {target_group['DisplayName']}"
            )
            memberships_created.append(matching_target_user["UserName"])
    logger.info(
        f"create_group_memberships:Finished adding {len(memberships_created)} users to group {target_group['DisplayName']}."
    )
    return memberships_created


def delete_group_memberships(group, users_to_remove, enable_membership_delete=False):
    """Delete group memberships for the users in the identity store.

    Args:
        group (dict): The group to remove the users from.
        users_to_remove (list): A list of users to remove from the group.
        enable_membership_delete (bool): Enable deletion of group memberships.

    Returns:
        list: A list of group membership ID for memberships deleted.
    """
    memberships_deleted = []
    logger.info(
        f"delete_group_memberships:Removing {len(users_to_remove)} users from group {group['DisplayName']}"
    )
    for user in users_to_remove:
        if enable_membership_delete and not DRY_RUN:
            response = identity_store.delete_group_membership(user["MembershipId"])

            if response:
                memberships_deleted.append(user["MemberId"]["UserName"])
                logger.info(
                    f"delete_group_memberships:Successfully removed user {user['MemberId']['UserName']} from group {group['DisplayName']}"
                )
            else:
                logger.error(
                    f"delete_group_memberships:Failed to remove user {user['MemberId']['UserName']} from group {group['DisplayName']}"
                )
        else:
            logger.info(
                f"delete_group_memberships:DRY_RUN:Successfully removed user {user['MemberId']['UserName']} from group {group['DisplayName']}"
            )
            memberships_deleted.append(user["MemberId"]["UserName"])
    logger.info(
        f"delete_group_memberships:Finished removing {len(memberships_deleted)} users from group {group['DisplayName']}"
    )
    return memberships_deleted


def sync_groups(source_groups, target_groups, target_users, **kwargs):
    """Sync the groups in the identity store.

    Args:
        source_groups (list): A list of groups from the source system.
        target_groups (list): A list of groups in the identity store.
        target_users (list): A list of users in the identity store.
        enable_membership_delete (bool): Enable deletion of group memberships.

    Returns:
        tuple: A tuple containing the groups memberships created and deleted.
    """
    enable_membership_delete = kwargs.get("enable_membership_delete", False)

    source_groups_to_sync, target_groups_to_sync = filters.compare_lists(
        {"values": source_groups, "key": "DisplayName"},
        {"values": target_groups, "key": "DisplayName"},
        mode="match",
    )
    logger.info(
        f"synchronize:groups:Found {len(source_groups_to_sync)} Source Groups and {len(target_groups_to_sync)} Target Groups"
    )

    groups_memberships_created = []
    groups_memberships_deleted = []
    for i in range(len(source_groups_to_sync)):
        if (
            source_groups_to_sync[i]["DisplayName"]
            == target_groups_to_sync[i]["DisplayName"]
        ):
            logger.info(
                f"synchronize:groups:Syncing group {source_groups_to_sync[i]['name']} with {target_groups_to_sync[i]['DisplayName']}"
            )
            users_to_add, users_to_remove = filters.compare_lists(
                {"values": source_groups_to_sync[i]["members"], "key": "primaryEmail"},
                {
                    "values": target_groups_to_sync[i]["GroupMemberships"],
                    "key": "MemberId.UserName",
                },
                mode="sync",
            )
            memberships_created = create_group_memberships(
                target_groups_to_sync[i], users_to_add, target_users
            )
            groups_memberships_created.extend(memberships_created)
            memberships_deleted = delete_group_memberships(
                target_groups_to_sync[i],
                users_to_remove,
                enable_membership_delete=enable_membership_delete,
            )
            groups_memberships_deleted.extend(memberships_deleted)

    return groups_memberships_created, groups_memberships_deleted
