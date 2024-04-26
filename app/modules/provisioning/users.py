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
