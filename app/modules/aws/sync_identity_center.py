import json
from logging import getLogger
from integrations.aws import identity_store
from modules.provisioning import users, groups
from utils import filters


logger = getLogger(__name__)


def synchronize(**kwargs):
    """Sync the AWS Identity Center with the Google Workspace."""
    sync_users = kwargs.get("sync_users", False)
    sync_groups = kwargs.get("sync_groups", False)
    query = kwargs.get("query", "email:aws-*")

    users_sync_status = None
    groups_sync_status = None

    source_groups = groups.get_groups_with_members_from_integration(
        "google_groups", query=query, filters=[lambda group: "AWS-" in group["name"]]
    )

    logger.info(f"Found {len(source_groups)} Source Groups")

    if sync_users:
        source_users = users.get_unique_users_from_groups(source_groups, "members")

        logger.info(f"Found {len(source_users)} Source Users")

        target_users = identity_store.list_users()
        logger.info(f"Found {len(target_users)} Target Users")

        users_to_create, users_to_delete = filters.compare_lists(
            {"values": source_users, "key": "primaryEmail"},
            {"values": target_users, "key": "UserName"},
            mode="sync",
            enable_delete=True,
        )
        logger.info(f"{len(users_to_create)} Users to Create")
        logger.info(f"{len(users_to_delete)} Users to Delete")

        created_users = create_aws_users(users_to_create)
        deleted_users = delete_aws_users(users_to_delete)

        logger.info(
            f"Users Sync Status: \n{len(created_users)} created\n{len(deleted_users)} deleted"
        )
        users_sync_status = created_users, deleted_users

    if sync_groups:
        target_groups = groups.get_groups_with_members_from_integration(
            "aws_identity_center"
        )
        logger.info(f"Found {len(target_groups)} Target Groups")
        logger.info("DEBUG: Target Groups")
        logger.info(json.dumps(target_groups[0], indent=2))
        for group in source_groups:
            group["DisplayName"] = group["name"].replace("AWS-", "")
        source_groups_to_sync, target_groups_to_sync = filters.compare_lists(
            {"values": source_groups, "key": "DisplayName"},
            {"values": target_groups, "key": "DisplayName"},
            mode="match",
        )
        logger.info(f"Found {len(source_groups_to_sync)} Source Groups to Sync")
        logger.info(f"Found {len(target_groups_to_sync)} Target Groups to Sync")
        for i in range(len(source_groups_to_sync)):
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
                )
                logger.info(
                    f"Adding {len(users_to_add)} users to group {target_groups_to_sync[i]['DisplayName']}"
                )
                create_group_memberships(source_groups_to_sync[i], users_to_add)
                delete_group_memberships(
                    target_groups_to_sync[i]["GroupId"], users_to_remove
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
    """TODO: Function not currently implemented.

    Waiting for full users creation implementation as it has the potential to delete all users in the identity store.
    """
    users_deleted = []
    for user in users_to_delete:
        # user_id = identity_store.get_user_id(user["UserName"])
        logger.info(f"Deleting user:\n{json.dumps(user, indent=2)}")
        # response = identity_store.delete_user(user["UserId"])
        response = True
        if response:
            users_deleted.append(user)
    return users_deleted


def create_group_memberships(group, users_to_add):
    group_id = identity_store.get_group_id(group["DisplayName"])
    for user in users_to_add:
        logger.info(f"Adding user {user['name']['givenName']} to group {group_id}")
        identity_store.create_group_membership(group_id, user["UserId"])


def delete_group_memberships(group_id, users_to_remove):
    for user in users_to_remove:
        membership_id = identity_store.get_group_membership_id(group_id, user["UserId"])
        if membership_id:
            identity_store.delete_group_membership(membership_id)
        logger.info(f"Deleting membership with ID {membership_id}")
        # identity_store.delete_group_membership(membership_id)
