from functools import reduce

from logging import getLogger


logger = getLogger(__name__)


def filter_by_condition(list, condition):
    """Filter a list by a condition, keeping only the items that satisfy the condition."""
    return [item for item in list if condition(item)]


def get_nested_value(dictionary, key):
    try:
        return reduce(dict.get, key.split("."), dictionary)
    except TypeError:
        logger.error(f"Error getting nested value for key: {key}")
        return None


def get_unique_users_from_groups(groups, key):
    users = set()
    for group in groups:
        group_users = get_nested_value(group, key)
        if group_users:
            users.update(tuple(user.items()) for user in group_users)
    return [dict(user) for user in users]


def sync_users(source, target, **kwargs):
    """
    Sync users from source to target systems. The function compares the users in the source and target systems and returns the users to create and the users to delete in the target system.

    Users to create are the ones that are in the source system but not in the target system.

    Users to delete are the ones that are in the target system but not in the source system.

    Args:
        source (dict): Source system data. Must contain the keys 'users' (list) and 'key' (string).
        target (dict): Target system data. Must contain the keys 'users' (list) and 'key' (string).
        filters (list): List of filters to apply to the users.

    Returns:
        tuple: A tuple containing the users to create and the users to delete in the target system.
    """

    source_key = source.get("key", None)
    target_key = target.get("key", None)
    source_users = source.get("users", None)
    target_users = target.get("users", None)
    enable_delete = kwargs.get("enable_delete", False)
    delete_target_all = kwargs.get("delete_target_all", False)

    # specifically handle the case where all the target system users should be deleted
    if delete_target_all:
        logger.warning("Marking all target system users for deletion.")
        return [], target_users

    # missing required data will result in no users to create or delete
    if not source_key or not target_key or not source_users:
        return [], []

    users_to_create = source_users.copy()

    logger.info(
        f"Syncing users from source ({len(source_users)}) to target ({len(target_users)})."
    )
    filters = kwargs.get("filters", [])
    for filter in filters:
        users_to_create = filter_by_condition(users_to_create, filter)

    target_users_keys = set(
        [get_nested_value(user, target_key) for user in target_users]
    )

    users_to_create = filter_by_condition(
        users_to_create,
        lambda user: get_nested_value(user, source_key) not in target_users_keys,
    )

    users_to_create_keys = set(
        [get_nested_value(user, source_key) for user in users_to_create]
    )

    users_to_delete = filter_by_condition(
        target_users,
        lambda user: get_nested_value(user, target_key) in users_to_create_keys,
    )

    if not enable_delete:
        users_to_delete = []

    return users_to_create, users_to_delete
