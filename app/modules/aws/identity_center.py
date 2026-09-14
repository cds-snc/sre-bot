"""Module to sync the AWS Identity Center with the Google Workspace."""

from typing import Any

import structlog

from modules.provisioning import entities, groups, users
from packages.aws_platform.adapters.identity_center import build_identity_center_adapter
from utils import filters

logger = structlog.get_logger()


# provision_entities splats each whole entity dict into the callable and treats a falsy
# return as a failed entity, so these bridges absorb the keys the adapter does not take
# and turn a non-success result into False.


def _create_user(email: str, first_name: str, family_name: str, **_ignored: Any) -> str | bool:
    """Create an Identity Center user; returns the UserId, or False on failure.

    An "already exists" ConflictException arrives as PERMANENT_ERROR and is
    returned as False, so the entity is recorded as failed and the sync continues.
    """
    result = build_identity_center_adapter().create_user(email=email, first_name=first_name, family_name=family_name)
    if not result.is_success:
        logger.error("create_user_failed", status=result.status.value, error_code=result.error_code, error=result.message)
        return False
    return result.data or False


def _delete_user(user_id: str, **_ignored: Any) -> bool:
    """Delete an Identity Center user; returns True, or False on failure."""
    result = build_identity_center_adapter().delete_user(user_id=user_id)
    if not result.is_success:
        logger.error("delete_user_failed", status=result.status.value, error_code=result.error_code, error=result.message)
        return False
    return bool(result.data)


def _create_group_membership(group_id: str, user_id: str, **_ignored: Any) -> str | bool:
    """Add a user to a group; returns the MembershipId, or False on failure.

    An "already exists" ConflictException arrives as PERMANENT_ERROR and is
    returned as False, so the entity is recorded as failed and the sync continues.
    """
    result = build_identity_center_adapter().create_group_membership(group_id=group_id, user_id=user_id)
    if not result.is_success:
        logger.error(
            "create_group_membership_failed",
            status=result.status.value,
            error_code=result.error_code,
            error=result.message,
        )
        return False
    return result.data or False


def _delete_group_membership(membership_id: str, **_ignored: Any) -> bool:
    """Remove a group membership; returns True, or False on failure."""
    result = build_identity_center_adapter().delete_group_membership(membership_id=membership_id)
    if not result.is_success:
        logger.error(
            "delete_group_membership_failed",
            status=result.status.value,
            error_code=result.error_code,
            error=result.message,
        )
        return False
    return bool(result.data)


def _list_target_users(log: Any) -> list[dict[str, Any]]:
    """List every Identity Center user.

    Raises:
        DirectoryUsersUnavailableError: when the listing fails.
    """
    result = build_identity_center_adapter().list_users()
    if not result.is_success:
        log.error("list_users_failed", error_code=result.error_code, error=result.message)
        raise users.DirectoryUsersUnavailableError(result.message, result.error_code)
    return result.data or []


def synchronize(
    enable_users_sync: bool = True,
    enable_user_create: bool = True,
    enable_user_delete: bool = False,
    enable_groups_sync: bool = True,
    enable_membership_create: bool = True,
    enable_membership_delete: bool = False,
    query: str = "email:aws-*",
    pre_processing_filters: list | None = None,
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

    log = logger.bind(
        enable_users_sync=enable_users_sync,
        enable_groups_sync=enable_groups_sync,
        enable_user_create=enable_user_create,
        enable_user_delete=enable_user_delete,
        enable_membership_create=enable_membership_create,
        enable_membership_delete=enable_membership_delete,
        query=query,
    )
    if pre_processing_filters is None:
        pre_processing_filters = []
    log.info(
        "synchronize_task_requested",
        pre_processing_filters_count=len(pre_processing_filters),
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
    log.info(
        "source_groups_users_fetched",
        groups_count=len(source_groups),
        users_count=len(source_users),
        source="google_groups",
    )
    target_groups = groups.get_groups_from_integration("aws_identity_center", pre_processing_filters=pre_processing_filters)
    target_users = _list_target_users(log)
    log.info(
        "target_groups_users_fetched",
        groups_count=len(target_groups),
        users_count=len(target_users),
        source="aws_identity_center",
    )
    if enable_users_sync:
        users_sync_status = sync_users(source_users, target_users, enable_user_create, enable_user_delete)
        target_users = _list_target_users(log)

    if enable_groups_sync:
        groups_sync_status = sync_groups(
            source_groups,
            target_groups,
            target_users,
            enable_membership_create,
            enable_membership_delete,
        )
    log.info(
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
        _create_user,
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
        _delete_user,
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
    source_groups = filters.preformat_items(source_groups, "name", "DisplayName", pattern=r"^AWS-", replace="")
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
    for i, source_group in enumerate(source_groups_to_sync):
        target_group = target_groups_to_sync[i]
        if source_group["DisplayName"] == target_group["DisplayName"]:
            logger.info(
                "groups_memberships_sync_processing",
                source_group_name=source_group["DisplayName"],
                target_group_name=target_group["DisplayName"],
            )
            users_to_add, users_to_remove = filters.compare_lists(
                {"values": source_group["members"], "key": "primaryEmail"},
                {
                    "values": target_group["GroupMemberships"],
                    "key": "MemberId.UserName",
                },
                mode="sync",
            )
            # source user for each group membership to add should exist in the target users list
            users_to_add = [
                {
                    **user,
                    "user_id": target_user["UserId"],
                    "group_id": target_group["GroupId"],
                    "log_user_name": user["primaryEmail"],
                    "log_group_name": target_group["DisplayName"],
                }
                for user in users_to_add
                for target_user in target_users
                if user.get("primaryEmail") == target_user["UserName"]
            ]

            memberships_created = entities.provision_entities(
                _create_group_membership,
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
                    "log_group_name": target_group["DisplayName"],
                }
                for user in users_to_remove
                if user.get("MembershipId")
            ]
            memberships_deleted = entities.provision_entities(
                _delete_group_membership,
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
        requested_emails = {email.lower() for email in users_emails}
        # "primaryEmail" is our own payload key here, resolved by display_key for logging.
        users_to_create = [
            {
                "primaryEmail": user.email,
                "email": user.email,
                "log_user_name": user.email,
                "first_name": user.given_name,
                "family_name": user.family_name,
            }
            for user in source_users
            if user.email.lower() in requested_emails
        ]

        return entities.provision_entities(
            _create_user,
            users_to_create,
            execute=True,
            integration_name="AWS",
            operation_name="Creation",
            entity_name="User",
            display_key="primaryEmail",
        )
    else:
        target_users = users.get_users_from_integration("aws_identity_center")
        users_to_delete = [user for user in target_users if user["UserName"] in users_emails]
        preformatting_keys = [
            ("UserId", "user_id"),
            ("UserName", "log_user_name"),
        ]
        for old_key, new_key in preformatting_keys:
            users_to_delete = filters.preformat_items(users_to_delete, old_key, new_key)

        return entities.provision_entities(
            _delete_user,
            users_to_delete,
            execute=True,
            integration_name="AWS",
            operation_name="Deletion",
            entity_name="User",
            display_key="UserName",
        )
