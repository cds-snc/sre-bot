# from logging import getLogger
import logging


logger = logging.getLogger(__name__)

DISPLAY_KEYS = {"aws": "UserName", "google": "primaryEmail"}


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
