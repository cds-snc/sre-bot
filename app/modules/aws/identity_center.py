"""Module to sync the AWS Identity Center with the Google Workspace."""
from logging import getLogger
from integrations.aws import identity_store
from modules.provisioning import groups, entities
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
    enable_user_create = kwargs.pop("enable_user_create", True)
    enable_user_delete = kwargs.pop("enable_user_delete", False)
    enable_groups_sync = kwargs.pop("enable_groups_sync", True)
    enable_membership_create = kwargs.pop("enable_membership_create", True)
    enable_membership_delete = kwargs.pop("enable_membership_delete", False)
    query = kwargs.pop("query", "email:aws-*")

    users_sync_status = None
    groups_sync_status = None

    source_groups_filters = [lambda group: "AWS-" in group["name"]]
    source_groups = groups.get_groups_from_integration(
        "google_groups", query=query, processing_filters=source_groups_filters
    )
    source_users = filters.get_unique_nested_dicts(source_groups, "members")
    logger.info(
        f"synchronize:Found {len(source_groups)} Groups and {len(source_users)} Users from Source"
    )

    target_groups = groups.get_groups_from_integration("aws_identity_center")
    target_users = identity_store.list_users()

    logger.info(
        f"synchronize:Found {len(target_groups)} Groups and {len(target_users)} Users from Target"
    )

    if enable_users_sync:
        users_sync_status = sync_users(
            source_users, target_users, enable_user_create, enable_user_delete, **kwargs
        )
        target_users = identity_store.list_users()

    if enable_groups_sync:
        groups_sync_status = sync_groups(
            source_groups,
            target_groups,
            target_users,
            enable_membership_create,
            enable_membership_delete,
            **kwargs,
        )
    logger.info("synchronize:Sync Completed")

    return {
        "users": users_sync_status,
        "groups": groups_sync_status,
    }


def sync_users(
    source_users,
    target_users,
    enable_user_create=True,
    enable_user_delete=False,
    **kwargs,
):
    """Sync the users in the identity store.

    Args:

        source_users (list): A list of users from the source system.
        target_users (list): A list of users in the identity store.
        enable_user_delete (bool): Enable deletion of users.
        delete_target_all (bool): Mark all target users for deletion.

    Returns:
        tuple: A tuple containing the users created and deleted.
    """
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
    preformatting_keys = [
        ("primaryEmail", "email"),
        ("primaryEmail", "log_user_name"),
        ("name.givenName", "first_name"),
        ("name.familyName", "family_name"),
    ]
    for old_key, new_key in preformatting_keys:
        users_to_create = filters.preformat_items(users_to_create, old_key, new_key)

    created_users = entities.provision_entities(
        identity_store.create_user,
        users_to_create,
        execute=enable_user_create,
        integration_name="AWS",
        operation_name="Creation",
        entity_name="User",
        display_key="primaryEmail",
    )
    preformatting_keys = [
        ("UserId", "user_id"),
        ("UserName", "log_user_name"),
    ]
    for old_key, new_key in preformatting_keys:
        users_to_delete = filters.preformat_items(users_to_delete, old_key, new_key)

    deleted_users = entities.provision_entities(
        identity_store.delete_user,
        users_to_delete,
        execute=enable_user_delete,
        integration_name="AWS",
        operation_name="Deletion",
        entity_name="User",
        display_key="UserName",
    )

    return created_users, deleted_users


def sync_groups(
    source_groups,
    target_groups,
    target_users,
    enable_membership_create=True,
    enable_membership_delete=False,
    **kwargs,
):
    """Sync the groups in the identity store.

    Args:
        source_groups (list): A list of groups from the source system.
        target_groups (list): A list of groups in the identity store.
        target_users (list): A list of users in the identity store.
        enable_membership_delete (bool): Enable deletion of group memberships.

    Returns:
        tuple: A tuple containing the groups memberships created and deleted.
    """
    logger.info("synchronize:groups:Formatting Source Groups")
    source_groups = filters.preformat_items(
        source_groups, "name", "DisplayName", pattern=r"^AWS-", replace=""
    )
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
            # source user for each group membership to add should exist in the target users list
            users_to_add = [
                {
                    **user,
                    "user_id": target_user["UserId"],
                    "group_id": target_groups_to_sync[i]["GroupId"],
                    "log_user_name": user["primaryEmail"],
                    "log_group_name": target_groups_to_sync[i]["DisplayName"],
                }
                for user in users_to_add
                for target_user in target_users
                if user.get("primaryEmail") == target_user["UserName"]
            ]

            memberships_created = entities.provision_entities(
                identity_store.create_group_membership,
                users_to_add,
                execute=enable_membership_create,
                integration_name="AWS",
                operation_name="Creation",
                entity_name="Group_Membership",
                display_key="primaryEmail",
            )
            groups_memberships_created.extend(memberships_created)

            users_to_remove = [
                {
                    **user,
                    "membership_id": user["MembershipId"],
                    "log_user_name": user["MemberId"]["UserName"],
                    "log_group_name": target_groups_to_sync[i]["DisplayName"],
                }
                for user in users_to_remove
                if user.get("MembershipId")
            ]
            memberships_deleted = entities.provision_entities(
                identity_store.delete_group_membership,
                users_to_remove,
                execute=enable_membership_delete,
                integration_name="AWS",
                operation_name="Deletion",
                entity_name="Group_Membership",
                display_key="MemberId.UserName",
            )
            groups_memberships_deleted.extend(memberships_deleted)

    return groups_memberships_created, groups_memberships_deleted
