"""This module contains utility functions for filtering lists and dictionaries."""
from functools import reduce
import logging

logger = logging.getLogger(__name__)


def filter_by_condition(list, condition):
    """Filter a list by a condition, keeping only the items that satisfy the condition."""
    return [item for item in list if condition(item)]


def get_nested_value(dictionary, key):
    if key in dictionary:
        return dictionary[key]
    try:
        return reduce(dict.get, key.split("."), dictionary)
    except TypeError:
        logger.error(f"Error getting nested value for key: {key}")
        return None


def compare_lists(source, target, mode="sync", **kwargs):
    """
    Compare two lists and return specific elements based on the comparison.

    Args:
        `source (dict)`: Source system data. Must contain the keys 'values' (list) and 'key' (string).
        `target (dict)`: Target system data. Must contain the keys 'values' (list) and 'key' (string).
        `mode (str)`: The mode of operation. 'sync' for sync operation and 'match' for match operation.

        **kwargs: Additional keyword arguments. Supported arguments are:

        - `filters (list)`: List of filters to apply to the users.
        - `enable_delete (bool)`: Enable the deletion of users in the target system.
        - `delete_target_all (bool)`: Mark all target system users for deletion.

    Returns:
        `tuple`:
            In `sync` mode, a tuple containing the elements to add and the elements to remove in the target system.

            In `match` mode, a tuple containing the elements that match between the source and target lists.
    """
    source_key = source.get("key", None)
    target_key = target.get("key", None)
    source_values = source.get("values", None)
    target_values = target.get("values", None)

    if not source_key or not target_key:
        return [], []

    filtered_source_values = {
        get_nested_value(value, source_key): value for value in source_values
    }
    filtered_target_values = {
        get_nested_value(value, target_key): value for value in target_values
    }

    if mode == "sync":
        enable_delete = kwargs.get("enable_delete", False)
        delete_target_all = kwargs.get("delete_target_all", False)

        if delete_target_all:
            return [], target_values

        users_to_add = [
            filtered_source_values[key]
            for key in filtered_source_values
            if key not in filtered_target_values
        ]
        users_to_remove = [
            filtered_target_values[key]
            for key in filtered_target_values
            if key not in filtered_source_values
        ]

        if not enable_delete:
            users_to_remove = []

        return users_to_add, users_to_remove

    elif mode == "match":
        matching_values = set(filtered_source_values.keys()) & set(
            filtered_target_values.keys()
        )

        filtered_source_groups = [
            filtered_source_values[value] for value in matching_values
        ]
        filtered_target_groups = [
            filtered_target_values[value] for value in matching_values
        ]

        return filtered_source_groups, filtered_target_groups
