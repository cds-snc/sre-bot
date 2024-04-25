from logging import getLogger
from integrations.aws import identity_store
from integrations.google_workspace import google_directory
from modules.provisioning import users, groups
from modules.utils import filters as filter_tools


logger = getLogger(__name__)


def synchronize(**kwargs):
    """Sync the AWS Identity Center with the Google Workspace."""
    sync_users = kwargs.get("sync_users", False)
    sync_groups = kwargs.get("sync_groups", False)
    query = kwargs.get("query", "email:aws-*")

    source_users = []
    source_groups = get_source_groups_with_users(query=query)
    target_users = []
    target_groups = []

    if sync_users:
        source_users = users.get_unique_users_from_groups(source_groups, "members")
        target_users = identity_store.list_users()
        users_sync_status = sync_aws_users(source_users, target_users)
    else:
        users_sync_status = None

    if sync_groups:
        target_groups = identity_store.list_groups_with_memberships()
        groups_sync_status = sync_aws_groups_members(source_groups, target_groups)
    else:
        groups_sync_status = None

    return users_sync_status, groups_sync_status


def get_source_groups(query="email:aws-*", name_filter="AWS-"):
    """Get the source groups."""
    source_groups = google_directory.list_groups(query=query)
    source_groups = filter_tools.filter_by_condition(
        source_groups, lambda group: name_filter in group["name"]
    )
    return source_groups


def get_source_groups_with_users(query="email:aws-*", name_filter="AWS-"):
    """Get the source groups with their users."""
    source_groups = google_directory.list_groups_with_members(query=query)
    source_groups = filter_tools.filter_by_condition(
        source_groups, lambda group: name_filter in group["name"]
    )
    return source_groups


def create_aws_users(users_to_create):
    """Create the users in the identity store.

    Args:
        users_to_create (list): A list of users to create.

    Returns:
        list: A list of ID of the users created.
    """
    users_created = []
    if not users_to_create:
        logger.info("No users to create.")
    for user in users_to_create:
        logger.info(
            f"Creating user {user['name']['givenName']} {user['name']['familyName']}"
        )
        response = identity_store.create_user(
            user["primaryEmail"], user["name"]["givenName"], user["name"]["familyName"]
        )
        if response:
            users_created.append(response)

    return users_created


def delete_aws_users(users_to_delete):
    """TODO: Implement this function. Waiting for actual implementation as it has the potential to delete all users in the identity store."""
    users_deleted = []
    if not users_to_delete:
        logger.info("No users to delete.")
    for user in users_to_delete:
        user_id = identity_store.get_user_id(user["UserName"])
        logger.info(f"Deleting user with ID {user_id}")
        # identity_store.delete_user(user_id)
    return users_deleted


def delete_group_memberships(group_id, users_to_remove):
    for user in users_to_remove:
        membership_id = identity_store.get_group_membership_id(group_id, user["UserId"])
        if membership_id:
            identity_store.delete_group_membership(membership_id)
        logger.info(f"Deleting membership with ID {membership_id}")
        # identity_store.delete_group_membership(membership_id)


def sync_aws_users(
    source_users,
    target_users,
    enable_delete=True,
    delete_target_all=False,
):
    """Sync the users of the source groups to the identity store.

    Args:
        query (str, optional): The query to filter the Google groups. Defaults to "email:aws-*".

    Returns:
        tuple: A tuple with the number of users to create and the number of users to delete.
    """

    filters = []
    filters.extend(
        [
            lambda user: "+" not in user["primaryEmail"],
            # lambda user: "admin" not in user["email"],
            lambda user: "cds-snc.ca" in user["primaryEmail"],
        ]
    )

    # strip unused fields
    source_users = [
        {
            "id": user["id"],
            "primaryEmail": user["primaryEmail"],
            "name": google_directory.get_user(user["primaryEmail"])["name"],
        }
        for user in source_users
    ]

    # remove duplicate values from the list of users
    source_users = [
        i for n, i in enumerate(source_users) if i not in source_users[n + 1 :]
    ]

    users_to_create, users_to_delete = users.sync(
        {"users": source_users, "key": "primaryEmail"},
        {"users": target_users, "key": "UserName"},
        filters=filters,
        enable_delete=enable_delete,
        delete_target_all=delete_target_all,
    )

    users_created = create_aws_users(users_to_create)

    users_deleted = delete_aws_users(users_to_delete)

    return users_created, users_deleted


def get_matching_groups(source_groups, target_groups):
    """Get all AWS and Google Groups matching the naming convention."""

    for group in source_groups:
        group["DisplayName"] = (
            group["name"].replace("AWS-", "").replace("@cds-snc.ca", "")
        )

    target_groups_names = [group["DisplayName"] for group in target_groups]
    source_groups_names = [group["DisplayName"] for group in source_groups]

    matching_groups = set(target_groups_names).intersection(source_groups_names)

    filtered_target_groups = filter_tools.filter_by_condition(
        target_groups, lambda group: group["DisplayName"] in matching_groups
    ).sort(key=lambda group: group["DisplayName"])

    filtered_source_groups = filter_tools.filter_by_condition(
        source_groups, lambda group: group["DisplayName"] in matching_groups
    ).sort(key=lambda group: group["DisplayName"])

    return filtered_source_groups, filtered_target_groups


def sync_aws_groups_members(source_groups, target_groups):
    source_groups_to_sync, target_groups_to_sync = get_matching_groups(
        source_groups, target_groups
    )

    for i in range(len(source_groups_to_sync)):
        users_to_add, users_to_remove = users.sync(
            {"users": source_groups_to_sync[i], "key": "email"},
            {"users": target_groups_to_sync[i], "key": "UserName"},
            filters=[lambda user: "+" not in user["email"]],
        )

        if users_to_add:
            logger.info(
                f"Adding {len(users_to_add)} users to group {target_groups_to_sync['DisplayName']}"
            )
            for user in users_to_add:
                identity_store.create_group_membership(
                    target_groups_to_sync["GroupId"], user["UserId"]
                )
        if users_to_remove:
            logger.info(
                f"Removing {len(users_to_remove)} users from group {target_groups_to_sync['DisplayName']}"
            )
            delete_group_memberships(target_groups_to_sync["GroupId"], users_to_remove)

    return users_to_add, users_to_remove
