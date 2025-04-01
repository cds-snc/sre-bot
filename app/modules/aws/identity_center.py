"""Module to sync the AWS Identity Center with the Google Workspace."""

from integrations.aws import identity_store
from modules.provisioning import groups, entities, users
from utils import filters
from core.logging import get_module_logger

DRY_RUN = True
logger = get_module_logger()


def synchronize(
    enable_users_sync: bool = True,
    enable_user_create: bool = True,
    enable_user_delete: bool = False,
    enable_groups_sync: bool = True,
    enable_membership_create: bool = True,
    enable_membership_delete: bool = False,
    query: str = "email:aws-*",
    pre_processing_filters: list = [],
):
    """Sync the AWS Identity Center with the Google Workspace.

    Args:
        enable_users_sync (bool): Enable the synchronization of users. Default is True.
        enable_user_create (bool): Enable the creation of users. Default is True.
        enable_user_delete (bool): Enable the deletion of users. Default is False.
        enable_groups_sync (bool): Enable the synchronization of groups. Default is True.
        enable_membership_create (bool): Enable the creation of group memberships. Default is True.
        enable_membership_delete (bool): Enable the deletion of group memberships. Default is False.
        query (str): The query to search for groups.
        pre_processing_filters (list): List of filters to apply to the groups before processing the members.
    Returns:
        tuple: A tuple containing the users sync status and groups sync status.
    """

    logger.info(
        "synchronize_task_requested",
        enable_users_sync=enable_users_sync,
        enable_groups_sync=enable_groups_sync,
        enable_user_create=enable_user_create,
        enable_user_delete=enable_user_delete,
        enable_membership_create=enable_membership_create,
        enable_membership_delete=enable_membership_delete,
        query=query,
        pre_processing_filters=pre_processing_filters,
    )
    users_sync_status = None
    groups_sync_status = None

    source_groups_filters = [lambda group: "AWS-" in group["name"]]
    source_groups = groups.get_groups_from_integration(
        "google_groups",
        query=query,
        pre_processing_filters=pre_processing_filters,
        post_processing_filters=source_groups_filters,
    )
    source_users = filters.get_unique_nested_dicts(source_groups, "members")
    logger.info(
        "source_groups_users_fetched",
        groups_count=len(source_groups),
        users_count=len(source_users),
        source="google_groups",
    )
    target_groups = groups.get_groups_from_integration(
        "aws_identity_center", pre_processing_filters=pre_processing_filters
    )
    target_users = identity_store.list_users()
    logger.info(
        "target_groups_users_fetched",
        groups_count=len(target_groups),
        users_count=len(target_users),
        source="aws_identity_center",
    )
    if enable_users_sync:
        users_sync_status = sync_users(
            source_users, target_users, enable_user_create, enable_user_delete
        )
        target_users = identity_store.list_users()

    if enable_groups_sync:
        groups_sync_status = sync_groups(
            source_groups,
            target_groups,
            target_users,
            enable_membership_create,
            enable_membership_delete,
        )
    logger.info(
        "synchronize_task_completed",
        users_sync_status=users_sync_status,
        groups_sync_status=groups_sync_status,
    )

    return {
        "users": users_sync_status,
        "groups": groups_sync_status,
    }


def sync_users(
    source_users: list,
    target_users: list,
    enable_user_create: bool = True,
    enable_user_delete: bool = False,
    delete_target_all: bool = False,
):
    """Sync the users in the identity store.

    Args:

        source_users (list): A list of users from the source system.
        target_users (list): A list of users in the identity store.
        enable_user_create (bool): Enable creation of users. Default is True.
        enable_user_delete (bool): Enable deletion of users. Default is False.
        delete_target_all (bool): Mark all target users for deletion. Default is False.

    Returns:
        tuple: A tuple containing the users created and deleted.
    """
    logger.info(
        "synchronize_users_task_requested",
        enable_user_create=enable_user_create,
        enable_user_delete=enable_user_delete,
        delete_target_all=delete_target_all,
        source_users_count=len(source_users),
        target_users_count=len(target_users),
    )

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
        "synchronize_users_task_processing",
        users_to_create_count=len(users_to_create),
        users_to_delete_count=len(users_to_delete),
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

    logger.info(
        "synchronize_users_task_completed",
        created_users_count=len(created_users),
        deleted_users_count=len(deleted_users),
    )
    return created_users, deleted_users


def sync_groups(
    source_groups: list,
    target_groups: list,
    target_users: list,
    enable_membership_create: bool = True,
    enable_membership_delete: bool = False,
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
    logger.info(
        "synchronize_groups_task_requested",
        enable_membership_create=enable_membership_create,
        enable_membership_delete=enable_membership_delete,
        source_groups_count=len(source_groups),
        target_groups_count=len(target_groups),
    )
    logger.info(
        "synchronize_groups_comparison_started",
    )
    source_groups = filters.preformat_items(
        source_groups, "name", "DisplayName", pattern=r"^AWS-", replace=""
    )
    source_groups_to_sync, target_groups_to_sync = filters.compare_lists(
        {"values": source_groups, "key": "DisplayName"},
        {"values": target_groups, "key": "DisplayName"},
        mode="match",
    )
    logger.info(
        "synchronize_groups_comparison_completed",
        source_groups_to_sync_count=len(source_groups_to_sync),
        target_groups_to_sync_count=len(target_groups_to_sync),
    )

    groups_memberships_created = []
    groups_memberships_deleted = []
    for i in range(len(source_groups_to_sync)):
        if (
            source_groups_to_sync[i]["DisplayName"]
            == target_groups_to_sync[i]["DisplayName"]
        ):
            logger.info(
                "groups_memberships_sync_processing",
                source_group_name=source_groups_to_sync[i]["DisplayName"],
                target_group_name=target_groups_to_sync[i]["DisplayName"],
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

    logger.info(
        "synchronize_groups_task_completed",
        groups_memberships_created_count=len(groups_memberships_created),
        groups_memberships_deleted_count=len(groups_memberships_deleted),
    )
    return groups_memberships_created, groups_memberships_deleted


def provision_aws_users(operation, users_emails):
    """Provision users in the AWS Identity Center.

    Args:
        users_emails (list): A list of emails of the users to provision.

    Returns:
        dict: The response of the users created.
    """
    if operation not in ["create", "delete"]:
        raise ValueError("Invalid operation")

    if operation == "create":
        source_users = users.get_users_from_integration("google_directory")
        users_to_create = [
            user for user in source_users if user["primaryEmail"] in users_emails
        ]
        preformatting_keys = [
            ("primaryEmail", "email"),
            ("primaryEmail", "log_user_name"),
            ("name.givenName", "first_name"),
            ("name.familyName", "family_name"),
        ]
        for old_key, new_key in preformatting_keys:
            users_to_create = filters.preformat_items(users_to_create, old_key, new_key)

        return entities.provision_entities(
            identity_store.create_user,
            users_to_create,
            execute=True,
            integration_name="AWS",
            operation_name="Creation",
            entity_name="User",
            display_key="primaryEmail",
        )
    else:
        target_users = users.get_users_from_integration("aws_identity_center")
        users_to_delete = [
            user for user in target_users if user["UserName"] in users_emails
        ]
        preformatting_keys = [
            ("UserId", "user_id"),
            ("UserName", "log_user_name"),
        ]
        for old_key, new_key in preformatting_keys:
            users_to_delete = filters.preformat_items(users_to_delete, old_key, new_key)

        return entities.provision_entities(
            identity_store.delete_user,
            users_to_delete,
            execute=True,
            integration_name="AWS",
            operation_name="Deletion",
            entity_name="User",
            display_key="UserName",
        )
