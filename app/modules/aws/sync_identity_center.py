from logging import getLogger
from integrations.aws import identity_store
from integrations.google_workspace import google_directory
from modules.provisioning.sync_users import (
    sync_users,
    filter_by_condition,
    get_unique_users_from_groups,
)


logger = getLogger(__name__)


def get_source_groups(query="email:aws-*", name_filter="AWS-"):
    source_groups = google_directory.list_groups(query=query)
    source_groups = filter_by_condition(
        source_groups, lambda group: name_filter in group["name"]
    )

    return source_groups


def get_source_groups_with_users(query="email:aws-*", name_filter="AWS-"):
    source_groups = get_source_groups(query=query, name_filter=name_filter)
    for i in range(len(source_groups)):
        source_groups[i] = google_directory.add_users_to_group(source_groups[i], source_groups[i]["id"])

    return source_groups


def sync_aws_users(query="email:aws-*", enable_delete=False, delete_target_all=False):
    """Sync the users of the source groups to the identity store.

    Args:
        query (str, optional): The query to filter the Google groups. Defaults to "email:aws-*".

    Returns:
        tuple: A tuple with the number of users to create and the number of users to delete.
    """

    filters = []
    filters.extend(
        [
            lambda user: "+" not in user["email"],
            # lambda user: "admin" not in user["email"],
            lambda user: "cds-snc.ca" in user["email"],
        ]
    )

    source_groups = get_source_groups_with_users(query=query)

    source_users = get_unique_users_from_groups(source_groups, "members")

    # strip unused fields
    source_users = [
        {
            "id": user["id"],
            "email": user["email"],
            "name": google_directory.get_user(user["email"])["name"],
        }
        for user in source_users
    ]

    # remove duplicate values from the list
    source_users = [dict(t) for t in {tuple(d.items()) for d in source_users}]

    aws_users = identity_store.list_users()

    users_to_create, users_to_delete = sync_users(
        {"users": source_users, "key": "email"},
        {"users": aws_users, "key": "UserName"},
        filters=filters,
        enable_delete=enable_delete,
        delete_target_all=delete_target_all,
    )

    result = len(users_to_create), len(users_to_delete)

    if not users_to_create:
        logger.info("No users to create.")
    for user in users_to_create:
        logger.info(f"Creating user {user}")
        # response = identity_store.create_user(
        #     user["email"], user["name"]["givenName"], user["name"]["familyName"]
        # )

    if not users_to_delete:
        logger.info("No users to delete.")
    for user in users_to_delete and enable_delete:
        user_id = identity_store.get_user_id(user["UserName"])
        logger.info(f"Deleting user {user} with ID {user_id}")
        # identity_store.delete_user(user_id)

    return result


def get_matching_groups(source_groups, target_groups):
    """Get all AWS and Google Groups matching the naming convention."""
    aws_groups = identity_store.list_groups()
    google_groups = get_source_groups_with_users()

    for group in google_groups:
        group["DisplayName"] = (
            group["name"].replace("AWS-", "").replace("@cds-snc.ca", "")
        )

    aws_groups_names = [group["DisplayName"] for group in aws_groups]
    google_groups_names = [group["DisplayName"] for group in google_groups]

    matching_groups = set(aws_groups_names).intersection(google_groups_names)

    filtered_aws_groups = filter_by_condition(
        aws_groups, lambda group: group["DisplayName"] in matching_groups
    )

    filtered_google_groups = filter_by_condition(
        google_groups, lambda group: group["DisplayName"] in matching_groups
    )

    return filtered_google_groups, filtered_aws_groups


