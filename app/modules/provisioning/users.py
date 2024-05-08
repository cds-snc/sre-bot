# from logging import getLogger
import logging

from utils import filters as filter_tools


logger = logging.getLogger(__name__)

DISPLAY_KEYS = {"aws": "UserName", "google": "primaryEmail"}


def get_unique_users_from_groups(groups, key):
    """Get the unique users from a list of groups with the same data schema or a single group dict.
    Considers the whole object for uniqueness, not specific keys.

    Args:
        groups (list or dict): A list of groups or a single group.
        key (str): The key to get the users from the groups.

    Returns:
        list: A list of unique users from the groups
    """
    users_dict = {}
    if isinstance(groups, list):
        logger.info(f"Getting unique users from {len(groups)} groups.")
        for group in groups:
            for user in filter_tools.get_nested_value(group, key):
                if user:
                    users_dict[str(user)] = user
    elif isinstance(groups, dict):
        logger.info("Getting unique users from a single group.")
        for user in filter_tools.get_nested_value(groups, key):
            if user:
                users_dict[str(user)] = user
    logger.info(f"Found {len(users_dict)} unique users.")
    return list(users_dict.values())


def provision_users(
    integration, operation, function, users, display_key=None, **kwargs
):
    """Provision users in the specified integration's operation.

    Args:
        integration (str): The target integration intended for the users.
        operation (str): The operation to perform on the users.
        function (function): The function to perform on the users.
        users (list): A list of user objects to create.
        display_key (str): The key to display the user name.

    Returns:
        list: A list of created users objects.
    """
    provisioned_users = []
    logger.info(f"{integration}:Starting {operation} of {len(users)} user(s)")
    for user in users:
        logger.info(f"user's data:\n{user}")
        response = function(**user, **kwargs)
        if response:
            logger.info(
                f"{integration}:Successful {operation} of user {user[display_key] if display_key else user}"
            )
            provisioned_users.append({"user": user, "response": response})
        else:
            logger.error(
                f"{integration}:Failed {operation} user {user[display_key] if display_key else user}"
            )
    return provisioned_users
