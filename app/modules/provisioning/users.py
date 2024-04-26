from logging import getLogger

from utils import filters as filter_tools


logger = getLogger(__name__)


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
        for group in groups:
            for user in filter_tools.get_nested_value(group, key):
                if user:
                    users_dict[str(user)] = user
    elif isinstance(groups, dict):
        for user in filter_tools.get_nested_value(groups, key):
            if user:
                users_dict[str(user)] = user

    return list(users_dict.values())


# def sync(source, target, **kwargs):
#     """
#     Sync users from source to target groups. The function compares the users in the source and target lists and returns the users to add/create and the users to remove/delete in the target list.

#     Users to create are the ones that are in the source list but not in the target list.

#     Users to delete are the ones that are in the target list but not in the source list.

#     Args:
#         source (dict): Source system data. Must contain the keys 'users' (list) and 'key' (string).
#         target (dict): Target system data. Must contain the keys 'users' (list) and 'key' (string).
#         **kwargs: Additional keyword arguments. Supported arguments are:

#             - filters (list): List of filters to apply to the users.
#             - enable_delete (bool): Enable the deletion of users in the target system.
#             - delete_target_all (bool): Mark all target system users for deletion.

#     Returns:
#         tuple: A tuple containing the users to create and the users to delete in the target system.
#     """

#     source_key = source.get("key", None)
#     target_key = target.get("key", None)
#     source_users = source.get("users", None)
#     target_users = target.get("users", None)
#     enable_delete = kwargs.get("enable_delete", False)
#     delete_target_all = kwargs.get("delete_target_all", False)

#     logger.info(
#         f"Syncing users from source to target.\nSource: {json.dumps(source, indent=2)}\nTarget: {json.dumps(target, indent=2)}"
#     )

#     # specifically handle the case where all the target system users should be deleted
#     if delete_target_all:
#         logger.warning("Marking all target system users for deletion.")
#         return [], target_users

#     # missing required data will result in no users to create or delete
#     if not source_key or not target_key or not source_users:
#         return [], []

#     users_to_add = source_users.copy()

#     logger.info(
#         f"Syncing users from source ({len(source_users)}) to target ({len(target_users)})."
#     )
#     filters = kwargs.get("filters", [])
#     for filter in filters:
#         users_to_add = filter_tools.filter_by_condition(users_to_add, filter)

#     target_users_keys = set(
#         [filter_tools.get_nested_value(user, target_key) for user in target_users]
#     )

#     users_to_add = filter_tools.filter_by_condition(
#         users_to_add,
#         lambda user: filter_tools.get_nested_value(user, source_key)
#         not in target_users_keys,
#     )

#     users_to_add_keys = set(
#         [filter_tools.get_nested_value(user, source_key) for user in users_to_add]
#     )

#     users_to_remove = filter_tools.filter_by_condition(
#         target_users,
#         lambda user: filter_tools.get_nested_value(user, target_key)
#         in users_to_add_keys,
#     )

#     if not enable_delete:
#         users_to_remove = []

#     return users_to_add, users_to_remove
